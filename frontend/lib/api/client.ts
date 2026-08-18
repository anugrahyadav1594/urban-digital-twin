/**
 * Typed API client for FastAPI backend integration.
 * Every call attempts to reach the backend first, gracefully falling back to
 * deterministic in-memory execution when the backend is unreachable.
 */
import { API_BASE } from "../constants";
import { CITY, featureFromId } from "../city-model";
import { SCENARIOS, runAccessibility, runRisk, runSuitability } from "../mock";
import type { AnalysisResult, CityInfo, FeatureRecord, Scenario, SuitabilityRequest, Layer } from "@/types";

let backendUp: boolean | null = null;

/** Subscribers notified whenever backend reachability changes. */
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
      // A silent fallback to mock data is indistinguishable from real
      // results. Make it loud in the console as well as the UI.
      console.error(
        "[NAGAR-X] Backend unreachable at " + API_BASE +
        " - serving DEMO DATA. Results below are NOT from your database."
      );
    } else {
      console.info("[NAGAR-X] Backend connected at " + API_BASE);
    }
    listeners.forEach((fn) => fn(up));
  }
}

/**
 * Timeouts, in ms.
 *
 * A single 2.5 s budget was applied to every call, but real MCDA / network
 * analysis over the live graph takes 10-25 s, so those requests were always
 * aborted and silently replaced by mock results. Reads stay snappy; heavy
 * POSTs get a realistic budget.
 */
const T_PROBE = 3000;
const T_READ = 20000;
const T_ANALYSIS = 120000;

async function tryFetch<T>(
  path: string,
  init?: RequestInit,
  timeoutMs: number = T_READ
): Promise<T | null> {
  // Previously a single failure latched backendUp=false forever, so the app
  // stayed in demo mode even after the API came back. Always retry.
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), timeoutMs);
    const res = await fetch(API_BASE + path, {
      ...init,
      signal: ctrl.signal,
      headers: { "content-type": "application/json", ...(init?.headers || {}) }
    });
    clearTimeout(t);
    if (!res.ok) throw new Error(String(res.status));
    setBackendUp(true);
    return (await res.json()) as T;
  } catch {
    setBackendUp(false);
    return null;
  }
}

/** Probe readiness directly; used by the status banner on mount. */
export async function checkBackend(): Promise<boolean> {
  const r = await tryFetch<{ ready: boolean }>("/ready", undefined, T_PROBE);
  return r !== null;
}

export const isDemoMode = () => backendUp !== true;

export const api = {
  getCity: async (): Promise<CityInfo> => (await tryFetch<CityInfo>("/city")) ?? CITY,

  getFeature: async (id: string): Promise<FeatureRecord | null> =>
    (await tryFetch<FeatureRecord>("/features/" + id)) ?? featureFromId(id),

  listScenarios: async (): Promise<Scenario[]> => (await tryFetch<Scenario[]>("/scenarios")) ?? SCENARIOS,

  createScenario: async (name: string, horizon: number = 2035, populationGrowthPct: number = 2.5): Promise<any> =>
    (await tryFetch("/scenarios", { method: "POST", body: JSON.stringify({ name, horizon, populationGrowthPct }) })) ?? { scenario_id: 1, name, status: "created" },

  addScenarioChange: async (scenarioId: string, change: any): Promise<any> =>
    (await tryFetch(`/scenarios/${scenarioId}/changes`, { method: "POST", body: JSON.stringify(change) })) ?? { status: "logged" },

  evaluateScenario: async (scenarioId: string, facilityType: string = "hospital"): Promise<any> =>
    (await tryFetch(`/scenarios/${scenarioId}/evaluate?facility_type=${facilityType}`, { method: "POST" }, T_ANALYSIS)) ?? [],

  compareScenarios: async (scenarioIds: string[], facilityType: string = "hospital"): Promise<any> =>
    (await tryFetch("/scenarios/compare", { method: "POST", body: JSON.stringify({ scenario_ids: scenarioIds, facility_type: facilityType }) }, T_ANALYSIS)) ?? null,

  suitability: async (req: SuitabilityRequest, scenario: Scenario): Promise<AnalysisResult> =>
    (await tryFetch<AnalysisResult>("/planning/suitability", { method: "POST", body: JSON.stringify({ ...req, scenario_id: scenario.id }) }, T_ANALYSIS)) ??
    runSuitability(req, scenario),

  emergencyCatalogue: async (): Promise<any> =>
    (await tryFetch<any>("/emergency/catalogue")) ?? { hazards: [], measures: [] },

  emergencyRoute: async (body: any): Promise<any> =>
    await tryFetch<any>("/emergency/route", { method: "POST", body: JSON.stringify(body) }, T_ANALYSIS),

  simulateDisaster: async (body: any): Promise<any> =>
    await tryFetch<any>("/emergency/simulate", { method: "POST", body: JSON.stringify(body) }, T_ANALYSIS),

  accessibility: async (scenario: Scenario): Promise<AnalysisResult> =>
    (await tryFetch<AnalysisResult>("/analysis/accessibility", { method: "POST", body: JSON.stringify({ scenario_id: scenario.id }) }, T_ANALYSIS)) ??
    runAccessibility(scenario),

  emergency: async (scenario: Scenario): Promise<AnalysisResult> =>
    (await tryFetch<AnalysisResult>("/analysis/emergency", { method: "POST", body: JSON.stringify({ scenario_id: scenario.id }) }, T_ANALYSIS)) ??
    runAccessibility(scenario),

  risk: async (scenario: Scenario): Promise<AnalysisResult> =>
    (await tryFetch<AnalysisResult>("/analysis/risk", { method: "POST", body: JSON.stringify({ scenario_id: scenario.id }) }, T_ANALYSIS)) ??
    runRisk(scenario),

  simulationPopulation: async (baseYear: number = 2025, horizonYear: number = 2035, annualRate: number = 0.025): Promise<any> =>
    (await tryFetch("/simulation/population", { method: "POST", body: JSON.stringify({ base_year: baseYear, horizon_year: horizonYear, annual_rate: annualRate }) }, T_ANALYSIS)) ?? null,

  simulationFlood: async (floodLevelM: number = 1.5, returnPeriodYears: number = 50): Promise<any> =>
    (await tryFetch("/simulation/flood", { method: "POST", body: JSON.stringify({ flood_level_m: floodLevelM, return_period_years: returnPeriodYears }) }, T_ANALYSIS)) ?? null,

  optimizeFacilities: async (facilityType: string = "hospital", objective: string = "p_median", numFacilities: number = 3): Promise<any> =>
    (await tryFetch("/optimization/facility-location", { method: "POST", body: JSON.stringify({ facility_type: facilityType, objective, num_facilities: numFacilities }) }, T_ANALYSIS)) ?? null,

  /** Live layer inventory with real row counts from PostGIS. */
  listLayers: async (): Promise<Layer[] | null> => await tryFetch<Layer[]>("/layers"),

  /** layerId may carry a query string, e.g. "buildings?limit=6000". */
  getLayerGeoJSON: async (layerId: string): Promise<any> => {
    const [id, qs] = layerId.split("?");
    return (await tryFetch(`/layers/${id}/geojson${qs ? "?" + qs : ""}`, undefined, 60000)) ?? null;
  },

  getResult: async (resultId: string): Promise<any> =>
    (await tryFetch(`/results/${resultId}`)) ?? null,
};
