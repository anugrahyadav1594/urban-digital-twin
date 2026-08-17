/**
 * Thin API client. Every call tries the FastAPI backend first and falls back
 * to the deterministic mock engine when the backend is unreachable, so the
 * workspace is always demonstrable (offline / demo mode).
 */
import { API_BASE } from "../constants";
import { CITY, featureFromId } from "../city-model";
import { SCENARIOS, runAccessibility, runRisk, runSuitability } from "../mock";
import type { AnalysisResult, CityInfo, FeatureRecord, Scenario, SuitabilityRequest } from "@/types";

let backendUp: boolean | null = null;

async function tryFetch<T>(path: string, init?: RequestInit): Promise<T | null> {
  if (backendUp === false) return null;
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 1200);
    const res = await fetch(API_BASE + path, { ...init, signal: ctrl.signal, headers: { "content-type": "application/json", ...(init?.headers || {}) } });
    clearTimeout(t);
    if (!res.ok) throw new Error(String(res.status));
    backendUp = true;
    return (await res.json()) as T;
  } catch {
    backendUp = false;
    return null;
  }
}

export const isDemoMode = () => backendUp !== true;

export const api = {
  getCity: async (): Promise<CityInfo> => (await tryFetch<CityInfo>("/city")) ?? CITY,

  getFeature: async (id: string): Promise<FeatureRecord | null> =>
    (await tryFetch<FeatureRecord>("/features/" + id)) ?? featureFromId(id),

  listScenarios: async (): Promise<Scenario[]> => (await tryFetch<Scenario[]>("/scenarios")) ?? SCENARIOS,

  suitability: async (req: SuitabilityRequest, scenario: Scenario): Promise<AnalysisResult> =>
    (await tryFetch<AnalysisResult>("/planning/suitability", { method: "POST", body: JSON.stringify(req) })) ??
    runSuitability(req, scenario),

  accessibility: async (scenario: Scenario): Promise<AnalysisResult> =>
    (await tryFetch<AnalysisResult>("/analysis/accessibility", { method: "POST", body: "{}" })) ?? runAccessibility(scenario),

  risk: async (scenario: Scenario): Promise<AnalysisResult> =>
    (await tryFetch<AnalysisResult>("/analysis/risk", { method: "POST", body: "{}" })) ?? runRisk(scenario),

  agentPlan: async (prompt: string): Promise<any> =>
    await tryFetch<any>("/agents/plan", {
      method: "POST",
      body: JSON.stringify({ prompt }),
    })
};
