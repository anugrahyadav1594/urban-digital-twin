/**
 * Typed API client for FastAPI backend integration.
 * Every call attempts to reach the backend first.
 */
import { API_BASE } from "../constants";
import { CITY, featureFromId } from "../city-model";
import { SCENARIOS, runAccessibility, runRisk, runSuitability } from "../mock";
// Namespace import for runEmergency: it is referenced by the demo fallback but
// is not exported by every version of mock.ts, and a named import for a
// missing export is a hard compile error. This resolves at runtime instead.
import * as mockFallbacks from "../mock";
import type {
  AnalysisResult, CityInfo, FeatureRecord, Scenario, SuitabilityRequest, Layer, Job,
  WorkflowId, WorkflowStepResult, DecisionRecord, StartWorkflowRequest, PlanCandidatesRequest,
  PlanValidateRequest, PlanCommitRequest, StressSimulateRequest, StressRerouteRequest,
  StressMitigateRequest, ImproveGapRequest, ImprovePackageRequest, CompareEvaluateRequest,
  CompareSelectRequest, ExplainDecisionRequest
} from "@/types";

export const BACKEND_REQUIRED = process.env.NEXT_PUBLIC_BACKEND_REQUIRED !== "false";

let backendUp: boolean | null = null;

type BackendListener = (up: boolean) => void;
const listeners = new Set<BackendListener>();

export function onBackendStatus(fn: BackendListener): () => void {
  listeners.add(fn);
  if (backendUp !== null) fn(backendUp);
  return () => listeners.delete(fn);
}

function setBackendUp(up: boolean) {
  const changed = backendUp !== up;
  backendUp = up;
  if (changed) {
    if (!up) {
      console.error(
        "[NAGAR-X] Backend unreachable at " + API_BASE +
        (BACKEND_REQUIRED ? " - BACKEND REQUIRED MODE ACTIVE." : " - serving DEMO DATA.")
      );
    } else {
      console.info("[NAGAR-X] Backend connected at " + API_BASE);
    }
    listeners.forEach((fn) => fn(up));
  }
}

const T_PROBE = 3000;
const T_READ = 20000;
const T_ANALYSIS = 120000;

async function tryFetch<T>(
  path: string,
  init?: RequestInit,
  timeoutMs: number = T_READ
): Promise<T | null> {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), timeoutMs);
    const res = await fetch(API_BASE + path, {
      ...init,
      signal: ctrl.signal,
      headers: { "content-type": "application/json", ...(init?.headers || {}) }
    });
    clearTimeout(t);
    // Backend responded — it is up, even if status is 4xx/5xx
    setBackendUp(true);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as T;
  } catch (err: any) {
    // Only mark backend down on network/timeout errors, not HTTP error responses
    const msg = err?.message || "";
    if (!msg.startsWith("HTTP ")) {
      setBackendUp(false);
    }
    if (BACKEND_REQUIRED) {
      console.warn(`[API Error] Request to ${path} failed:`, err);
    }
    return null;
  }
}

export async function checkBackend(): Promise<boolean> {
  const r = await tryFetch<{ ready: boolean }>("/ready", undefined, T_PROBE);
  return r !== null;
}

export const isDemoMode = () => backendUp !== true && !BACKEND_REQUIRED;

/**
 * POST that surfaces the actual error.
 *
 * `tryFetch` returns null for every failure so the app can fall back to demo
 * data. That is right for city/layers, but for the emergency endpoints it made
 * a 404 (router not loaded), a 409 (no fire stations) and a dead socket all
 * look identical - the panel just said "unreachable".
 */
async function postStrict(path: string, body: unknown): Promise<any> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), T_ANALYSIS);
  let res: Response;
  try {
    res = await fetch(API_BASE + path, {
      method: "POST",
      body: JSON.stringify(body),
      signal: ctrl.signal,
      headers: { "content-type": "application/json" }
    });
  } catch (e: any) {
    clearTimeout(t);
    setBackendUp(false);
    throw new Error(
      e?.name === "AbortError"
        ? "Request timed out after 120 s."
        : `Cannot reach the API at ${API_BASE}. Is the backend running, and did you restart it?`
    );
  }
  clearTimeout(t);
  // The backend answered, so it is up regardless of status.
  setBackendUp(true);
  if (res.status === 404) {
    throw new Error(
      `404 from ${API_BASE}${path} - the backend is running but has no such ` +
      `route. The emergency router was not loaded: RESTART uvicorn.`
    );
  }
  if (!res.ok) {
    let detail = "";
    try { detail = (await res.json())?.detail ?? ""; } catch { /* non-JSON body */ }
    throw new Error(`HTTP ${res.status}${detail ? " - " + detail : ""}`);
  }
  return res.json();
}

export function parseApiError(payload: any, status: number): Error {
  if (!payload) return new Error(`HTTP ${status}`);
  const errDetail = payload.detail ?? payload.error ?? payload;
  if (typeof errDetail === "object" && errDetail !== null) {
    if (errDetail.error && typeof errDetail.error === "object") {
      const e = errDetail.error;
      const msg = e.message || e.code || `HTTP ${status}`;
      const err = new Error(msg);
      (err as any).code = e.code;
      (err as any).step = e.step;
      (err as any).details = e.details;
      return err;
    }
    const msg = errDetail.message || errDetail.error || JSON.stringify(errDetail);
    const err = new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
    if (errDetail.code) (err as any).code = errDetail.code;
    if (errDetail.step) (err as any).step = errDetail.step;
    if (errDetail.details) (err as any).details = errDetail.details;
    return err;
  }
  return new Error(typeof errDetail === "string" ? errDetail : `HTTP ${status}`);
}

async function postWorkflow<TRequest, TResponse>(
  path: string,
  body: TRequest,
  timeoutMs: number = T_ANALYSIS
): Promise<TResponse> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);

  try {
    const response = await fetch(API_BASE + path, {
      method: "POST",
      body: JSON.stringify(body),
      signal: ctrl.signal,
      headers: { "content-type": "application/json" }
    });

    setBackendUp(true);

    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }

    if (!response.ok) {
      throw parseApiError(payload, response.status);
    }

    return payload as TResponse;
  } catch (error: any) {
    if (error?.name === "AbortError") {
      throw new Error(`Workflow request to ${path} timed out after ${timeoutMs} ms.`);
    }
    const msg = error?.message || "";
    if (!msg.startsWith("HTTP ") && !msg.includes("timed out")) {
      setBackendUp(false);
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

async function getWorkflow<TResponse>(
  path: string,
  timeoutMs: number = T_READ
): Promise<TResponse> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);

  try {
    const response = await fetch(API_BASE + path, {
      method: "GET",
      signal: ctrl.signal,
      headers: { "content-type": "application/json" }
    });

    setBackendUp(true);

    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }

    if (!response.ok) {
      throw parseApiError(payload, response.status);
    }

    return payload as TResponse;
  } catch (error: any) {
    if (error?.name === "AbortError") {
      throw new Error(`Workflow request to ${path} timed out.`);
    }
    const msg = error?.message || "";
    if (!msg.startsWith("HTTP ")) {
      setBackendUp(false);
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}


export const api = {
  getCity: async (): Promise<CityInfo> => (await tryFetch<CityInfo>("/city")) ?? CITY,

  getFeature: async (id: string): Promise<FeatureRecord | null> =>
    (await tryFetch<FeatureRecord>("/features/" + id)) ?? featureFromId(id),

  listScenarios: async (): Promise<Scenario[]> => {
    const res = await tryFetch<Scenario[]>("/scenarios");
    if (res) return res;
    if (BACKEND_REQUIRED) throw new Error("Failed to fetch scenarios from backend");
    return SCENARIOS;
  },

  createScenario: async (name: string, horizon: number = 2035, populationGrowthPct: number = 2.5, description?: string): Promise<Scenario> => {
    const res = await tryFetch<Scenario>("/scenarios", {
      method: "POST",
      body: JSON.stringify({ name, horizon, populationGrowthPct, description })
    });
    if (res) return res;
    if (BACKEND_REQUIRED) throw new Error("Failed to create scenario on backend");
    return { id: `scn_${Date.now()}`, name, status: "draft", createdAt: new Date().toISOString(), horizon, populationGrowthPct, changes: [] };
  },

  updateScenario: async (scenarioId: string, updates: Partial<Scenario>): Promise<Scenario> => {
    const res = await tryFetch<Scenario>(`/scenarios/${scenarioId}`, {
      method: "PATCH",
      body: JSON.stringify(updates)
    });
    if (res) return res;
    if (BACKEND_REQUIRED) throw new Error("Failed to update scenario on backend");
    return { id: scenarioId, name: updates.name || "Scenario", status: updates.status || "draft", createdAt: "", horizon: updates.horizon || 2035, populationGrowthPct: updates.populationGrowthPct || 2.5, changes: [] };
  },

  addScenarioChange: async (scenarioId: string, change: { type: string; operation?: string; label?: string; parameters?: any; object_id?: number }): Promise<any> => {
    const res = await tryFetch(`/scenarios/${scenarioId}/changes`, {
      method: "POST",
      body: JSON.stringify({
        type: change.type,
        operation: change.operation || "INSERT",
        label: change.label,
        parameters: change.parameters || {},
        object_id: change.object_id
      })
    });
    if (res) return res;
    if (BACKEND_REQUIRED) throw new Error("Failed to log scenario change on backend");
    return { status: "logged" };
  },

  evaluateScenario: async (scenarioId: string, facilityType: string = "hospital"): Promise<any> =>
    (await tryFetch(`/scenarios/${scenarioId}/evaluate?facility_type=${facilityType}`, { method: "POST" }, T_ANALYSIS)) ?? [],

  compareScenarios: async (scenarioIds: string[], facilityType: string = "hospital"): Promise<any> => {
    const res = await tryFetch("/scenarios/compare", {
      method: "POST",
      body: JSON.stringify({ scenario_ids: scenarioIds, facility_type: facilityType })
    }, T_ANALYSIS);
    if (res) return res;
    if (BACKEND_REQUIRED) throw new Error("Failed to run scenario comparison on backend");
    return null;
  },

  roadProposal: async (req: { geometry: any; road_type: string; lanes: number; speed: number; scenario_id?: string }): Promise<AnalysisResult> => {
    const res = await tryFetch<AnalysisResult>("/planning/road", {
      method: "POST",
      body: JSON.stringify(req)
    }, T_ANALYSIS);
    if (res) return res;
    if (BACKEND_REQUIRED) throw new Error("Failed to compute road proposal on backend");
    throw new Error("Backend road analysis failed");
  },

  emergencyCatalogue: async (): Promise<any> =>
    (await tryFetch<any>("/emergency/catalogue")) ?? { hazards: [], measures: [] },

  // postStrict, not tryFetch: for these two an honest failure beats a silent
  // null that the panel can only report as "unreachable".
  emergencyRoute: async (body: any): Promise<any> =>
    await postStrict("/emergency/route", body),

  simulateDisaster: async (body: any): Promise<any> =>
    await postStrict("/emergency/simulate", body),

  suitability: async (req: SuitabilityRequest, scenario: Scenario): Promise<AnalysisResult> => {
    const res = await tryFetch<AnalysisResult>("/planning/suitability", {
      method: "POST",
      body: JSON.stringify({ ...req, scenario_id: scenario.id })
    }, T_ANALYSIS);
    if (res) return res;
    if (BACKEND_REQUIRED) throw new Error("Failed to compute site suitability on backend");
    return runSuitability(req, scenario);
  },

  accessibility: async (scenario: Scenario): Promise<AnalysisResult> => {
    const res = await tryFetch<AnalysisResult>("/analysis/accessibility", {
      method: "POST",
      body: JSON.stringify({ scenario_id: scenario.id })
    }, T_ANALYSIS);
    if (res) return res;
    if (BACKEND_REQUIRED) throw new Error("Failed to compute accessibility on backend");
    return runAccessibility(scenario);
  },

  emergency: async (scenario: Scenario): Promise<AnalysisResult> => {
    const res = await tryFetch<AnalysisResult>("/analysis/emergency", {
      method: "POST",
      body: JSON.stringify({ scenario_id: scenario.id })
    }, T_ANALYSIS);
    if (res) return res;
    if (BACKEND_REQUIRED) throw new Error("Failed to compute emergency response coverage on backend");
    const runEmergency = (mockFallbacks as any).runEmergency;
    return runEmergency ? runEmergency(scenario) : runAccessibility(scenario);
  },

  risk: async (scenario: Scenario): Promise<AnalysisResult> => {
    const res = await tryFetch<AnalysisResult>("/analysis/risk", {
      method: "POST",
      body: JSON.stringify({ scenario_id: scenario.id })
    }, T_ANALYSIS);
    if (res) return res;
    if (BACKEND_REQUIRED) throw new Error("Failed to compute network resilience on backend");
    return runRisk(scenario);
  },

  demand: async (scenario: Scenario): Promise<AnalysisResult> => {
    const res = await tryFetch<AnalysisResult>("/analysis/demand", {
      method: "POST",
      body: JSON.stringify({ scenario_id: scenario.id })
    }, T_ANALYSIS);
    if (res) return res;
    if (BACKEND_REQUIRED) throw new Error("Failed to compute infrastructure demand on backend");
    throw new Error("Backend demand analysis failed");
  },

  agentPlan: async (prompt: string): Promise<any> => {
    const res = await tryFetch<any>("/agents/plan", {
      method: "POST",
      body: JSON.stringify({ prompt }),
    }, T_ANALYSIS);
    if (res) return res;
    if (BACKEND_REQUIRED) throw new Error("Failed to execute AI plan on backend");
    return null;
  },

  simulationPopulation: async (baseYear: number = 2025, horizonYear: number = 2035, annualRate: number = 0.025): Promise<any> => {
    const res = await tryFetch("/simulation/population", {
      method: "POST",
      body: JSON.stringify({ base_year: baseYear, horizon_year: horizonYear, annual_rate: annualRate })
    }, T_ANALYSIS);
    if (res) return res;
    if (BACKEND_REQUIRED) throw new Error("Failed to run population simulation on backend");
    return null;
  },

  simulationFlood: async (floodLevelM: number = 1.5, returnPeriodYears: number = 50): Promise<any> => {
    const res = await tryFetch("/simulation/flood", {
      method: "POST",
      body: JSON.stringify({ flood_level_m: floodLevelM, return_period_years: returnPeriodYears })
    }, T_ANALYSIS);
    if (res) return res;
    if (BACKEND_REQUIRED) throw new Error("Failed to run flood exposure simulation on backend");
    return null;
  },

  optimizeFacilities: async (facilityType: string = "hospital", objective: string = "p_median", numFacilities: number = 3): Promise<any> => {
    const res = await tryFetch("/optimization/facility-location", {
      method: "POST",
      body: JSON.stringify({ facility_type: facilityType, objective, num_facilities: numFacilities })
    }, T_ANALYSIS);
    if (res) return res;
    if (BACKEND_REQUIRED) throw new Error("Failed to run facility location optimization on backend");
    return null;
  },

  createJob: async (title: string, kind: string, stages: any[]): Promise<Job> => {
    const res = await tryFetch<Job>("/jobs", {
      method: "POST",
      body: JSON.stringify({ title, kind, stages })
    });
    if (res) return res;
    if (BACKEND_REQUIRED) throw new Error("Failed to create job on backend");
    return {
      id: `job_${Date.now()}`,
      title,
      kind,
      progress: 0,
      state: "running",
      stages: stages.map((s, i) => ({ ...s, state: i === 0 ? "running" : "pending" })),
      startedAt: Date.now()
    };
  },

  getJob: async (jobId: string): Promise<Job | null> => {
    return await tryFetch<Job>(`/jobs/${jobId}`);
  },

  updateJob: async (jobId: string, update: { state?: string; progress?: number; error?: string; stages?: any[] }): Promise<Job | null> => {
    return await tryFetch<Job>(`/jobs/${jobId}`, {
      method: "PATCH",
      body: JSON.stringify(update)
    });
  },

  listLayers: async (): Promise<Layer[] | null> => await tryFetch<Layer[]>("/layers"),

  // ---- City scoring / development packages (product report S1-S3) ----

  /** The scoring framework itself: dimensions, units, benchmarks. */
  scoringDimensions: async (): Promise<any> =>
    await tryFetch("/scoring/dimensions"),

  /** City scorecard for a region, with benchmark comparison. */
  cityScore: async (region = "adivali_devad"): Promise<any> =>
    await tryFetch(`/scoring/city?region=${encodeURIComponent(region)}`,
                   undefined, T_ANALYSIS),

  /** Scorecard recomputed with custom dimension weights. */
  cityScoreWeighted: async (region: string, weights: Record<string, number>):
    Promise<any> => await postStrict("/scoring/city", { region, weights }),

  /** Generate a coordinated development package from the score gaps. */
  developmentPackage: async (body: {
    region?: string; targetUplift?: number; priorities?: string[];
    budget?: number | null; maxActions?: number;
    weights?: Record<string, number> | null;
  }): Promise<any> => await postStrict("/scoring/package", body),

  /** Build Scenario A/B/C and compare them on common KPIs. */
  comparePackages: async (body: {
    region?: string;
    variants?: Array<{ name: string; targetUplift?: number;
                       priorities?: string[]; budget?: number | null }>;
    weights?: Record<string, number> | null;
  }): Promise<any> => await postStrict("/scoring/compare", body),

  /** Comparison regions extracted by db/extract_batch.py. */
  listRegions: async (): Promise<any[]> => (await tryFetch<any[]>("/regions")) ?? [],

  /** One region as a single FeatureCollection (all layers, tagged). */
  getRegionGeoJSON: async (regionId: string): Promise<any> =>
    await tryFetch(`/regions/${regionId}/geojson`, undefined, T_ANALYSIS),

  getLayerGeoJSON: async (layerId: string): Promise<any> => {
    const [id, qs] = layerId.split("?");
    return (await tryFetch(`/layers/${id}/geojson${qs ? "?" + qs : ""}`, undefined, 60000)) ?? null;
  },

  getResult: async (resultId: string): Promise<any> =>
    (await tryFetch(`/results/${resultId}`)) ?? null,

  // --------------------------------------------------------------------------
  // BACKEND WORKFLOW API ADAPTERS
  //
  // Unified user flows (product report S4). These wrap the /workflows router:
  // a session is started, steps are driven through it, and the session id
  // carries state between steps so each flow leads into the next decision.
  // --------------------------------------------------------------------------
  startWorkflow: async (
    workflowId: WorkflowId,
    scenarioId?: string | number,
    initialContext?: Record<string, any>
  ): Promise<WorkflowStepResult> =>
    postWorkflow<StartWorkflowRequest, WorkflowStepResult>("/workflows/start", {
      workflow_id: workflowId,
      scenario_id: scenarioId,
      initial_context: initialContext ?? {}
    }),

  getWorkflowSession: async (sessionId: string): Promise<WorkflowStepResult> =>
    getWorkflow<WorkflowStepResult>(`/workflows/session/${sessionId}`),

  planCandidates: async (req: PlanCandidatesRequest): Promise<WorkflowStepResult> =>
    postWorkflow<PlanCandidatesRequest, WorkflowStepResult>("/workflows/plan/candidates", req, T_ANALYSIS),

  planValidate: async (req: PlanValidateRequest): Promise<WorkflowStepResult> =>
    postWorkflow<PlanValidateRequest, WorkflowStepResult>("/workflows/plan/validate", req),

  planCommit: async (req: PlanCommitRequest): Promise<WorkflowStepResult> =>
    postWorkflow<PlanCommitRequest, WorkflowStepResult>("/workflows/plan/commit", req),

  stressSimulate: async (req: StressSimulateRequest): Promise<WorkflowStepResult> =>
    postWorkflow<StressSimulateRequest, WorkflowStepResult>("/workflows/stress/simulate", req, T_ANALYSIS),

  stressReroute: async (req: StressRerouteRequest): Promise<WorkflowStepResult> =>
    postWorkflow<StressRerouteRequest, WorkflowStepResult>("/workflows/stress/reroute", req, T_ANALYSIS),

  stressMitigate: async (req: StressMitigateRequest): Promise<WorkflowStepResult> =>
    postWorkflow<StressMitigateRequest, WorkflowStepResult>("/workflows/stress/mitigate", req),

  improveAudit: async (sessionId: string): Promise<WorkflowStepResult> =>
    postWorkflow<Record<string, never>, WorkflowStepResult>(`/workflows/improve/audit/${sessionId}`, {}),

  improveGaps: async (req: ImproveGapRequest): Promise<WorkflowStepResult> =>
    postWorkflow<ImproveGapRequest, WorkflowStepResult>("/workflows/improve/gaps", req),

  improvePackage: async (req: ImprovePackageRequest): Promise<WorkflowStepResult> =>
    postWorkflow<ImprovePackageRequest, WorkflowStepResult>("/workflows/improve/package", req),

  improveSimulate: async (sessionId: string): Promise<WorkflowStepResult> =>
    postWorkflow<Record<string, never>, WorkflowStepResult>(`/workflows/improve/simulate/${sessionId}`, {}),

  improveCompare: async (sessionId: string): Promise<WorkflowStepResult> =>
    postWorkflow<Record<string, never>, WorkflowStepResult>(`/workflows/improve/compare/${sessionId}`, {}),

  improveCommit: async (sessionId: string): Promise<WorkflowStepResult> =>
    postWorkflow<Record<string, never>, WorkflowStepResult>(`/workflows/improve/commit/${sessionId}`, {}),

  compareEvaluate: async (req: CompareEvaluateRequest): Promise<WorkflowStepResult> =>
    postWorkflow<CompareEvaluateRequest, WorkflowStepResult>("/workflows/compare/evaluate", req, T_ANALYSIS),

  compareSelect: async (req: CompareSelectRequest): Promise<WorkflowStepResult> =>
    postWorkflow<CompareSelectRequest, WorkflowStepResult>("/workflows/compare/select", req),

  explainDecisionRecord: async (req: ExplainDecisionRequest): Promise<DecisionRecord> =>
    postWorkflow<ExplainDecisionRequest, DecisionRecord>("/workflows/explain/decision-record", req),
};