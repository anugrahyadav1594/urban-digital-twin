/**
 * Typed API client for FastAPI backend integration.
 * Every call attempts to reach the backend first, gracefully falling back to
 * deterministic in-memory execution when the backend is unreachable.
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
    const t = setTimeout(() => ctrl.abort(), 2500);
    const res = await fetch(API_BASE + path, {
      ...init,
      signal: ctrl.signal,
      headers: { "content-type": "application/json", ...(init?.headers || {}) }
    });
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

  createScenario: async (name: string, horizon: number = 2035, populationGrowthPct: number = 2.5): Promise<any> =>
    (await tryFetch("/scenarios", { method: "POST", body: JSON.stringify({ name, horizon, populationGrowthPct }) })) ?? { scenario_id: 1, name, status: "created" },

  addScenarioChange: async (scenarioId: string, change: any): Promise<any> =>
    (await tryFetch(`/scenarios/${scenarioId}/changes`, { method: "POST", body: JSON.stringify(change) })) ?? { status: "logged" },

  evaluateScenario: async (scenarioId: string, facilityType: string = "hospital"): Promise<any> =>
    (await tryFetch(`/scenarios/${scenarioId}/evaluate?facility_type=${facilityType}`, { method: "POST" })) ?? [],

  compareScenarios: async (scenarioIds: string[], facilityType: string = "hospital"): Promise<any> =>
    (await tryFetch("/scenarios/compare", { method: "POST", body: JSON.stringify({ scenario_ids: scenarioIds, facility_type: facilityType }) })) ?? null,

  suitability: async (req: SuitabilityRequest, scenario: Scenario): Promise<AnalysisResult> =>
    (await tryFetch<AnalysisResult>("/planning/suitability", { method: "POST", body: JSON.stringify({ ...req, scenario_id: scenario.id }) })) ??
    runSuitability(req, scenario),

  accessibility: async (scenario: Scenario): Promise<AnalysisResult> =>
    (await tryFetch<AnalysisResult>("/analysis/accessibility", { method: "POST", body: JSON.stringify({ scenario_id: scenario.id }) })) ??
    runAccessibility(scenario),

  emergency: async (scenario: Scenario): Promise<AnalysisResult> =>
    (await tryFetch<AnalysisResult>("/analysis/emergency", { method: "POST", body: JSON.stringify({ scenario_id: scenario.id }) })) ??
    runAccessibility(scenario),

  risk: async (scenario: Scenario): Promise<AnalysisResult> =>
    (await tryFetch<AnalysisResult>("/analysis/risk", { method: "POST", body: JSON.stringify({ scenario_id: scenario.id }) })) ??
    runRisk(scenario),

  simulationPopulation: async (baseYear: number = 2025, horizonYear: number = 2035, annualRate: number = 0.025): Promise<any> =>
    (await tryFetch("/simulation/population", { method: "POST", body: JSON.stringify({ base_year: baseYear, horizon_year: horizonYear, annual_rate: annualRate }) })) ?? null,

  simulationFlood: async (floodLevelM: number = 1.5, returnPeriodYears: number = 50): Promise<any> =>
    (await tryFetch("/simulation/flood", { method: "POST", body: JSON.stringify({ flood_level_m: floodLevelM, return_period_years: returnPeriodYears }) })) ?? null,

  optimizeFacilities: async (facilityType: string = "hospital", objective: string = "p_median", numFacilities: number = 3): Promise<any> =>
    (await tryFetch("/optimization/facility-location", { method: "POST", body: JSON.stringify({ facility_type: facilityType, objective, num_facilities: numFacilities }) })) ?? null,

  getLayerGeoJSON: async (layerId: string): Promise<any> =>
    (await tryFetch(`/layers/${layerId}/geojson`)) ?? null,

  getResult: async (resultId: string): Promise<any> =>
    (await tryFetch(`/results/${resultId}`)) ?? null,
};
