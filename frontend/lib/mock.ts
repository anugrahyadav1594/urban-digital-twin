/**
 * Deterministic "engine" that stands in for the backend during development.
 * Every function here has a 1:1 counterpart in lib/api/client.ts, so swapping
 * to the real FastAPI service is a matter of flipping DEMO_MODE off.
 */
import { CITY, FACILITIES, PARCELS, type Parcel } from "./city-model";
import { uid } from "./format";
import type { AnalysisResult, JobStage, Metric, Scenario, SuitabilityRequest } from "@/types";

const km = (a: { lon: number; lat: number }, b: { lon: number; lat: number }) =>
  Math.hypot((a.lon - b.lon) * 105.6, (a.lat - b.lat) * 111);

export const DEFAULT_WEIGHTS: Record<string, number> = {
  Population: 30, Accessibility: 20, "Land suitability": 20, "Flood risk": 15, "Existing coverage": 10, Environment: 5
};

export const SUITABILITY_STAGES: JobStage[] = [
  { key: "filter", label: "Candidate filtering", state: "pending" },
  { key: "access", label: "Accessibility analysis", state: "pending" },
  { key: "flood", label: "Flood constraint check", state: "pending" },
  { key: "optimize", label: "Multi-criteria optimisation", state: "pending" },
  { key: "validate", label: "Validation", state: "pending" }
];

function popWithin(p: Parcel, radiusKm: number) {
  let s = 0;
  for (const q of PARCELS) if (km(p, q) < radiusKm) s += q.population;
  return s;
}

export function runSuitability(req: SuitabilityRequest, scenario: Scenario): AnalysisResult {
  const growth = 1 + scenario.populationGrowthPct / 100;
  const floodBlocked = req.floodRule === "Allow all" ? [] : req.floodRule === "Exclude High" ? ["High"] : ["High", "Medium"];
  const existing = FACILITIES.filter((f) => f.type === req.facility);

  const scored = PARCELS
    .filter((p) => p.areaM2 >= req.minArea)
    .filter((p) => !floodBlocked.includes(p.flood))
    .filter((p) => ["PS", "G1", "R1", "R2", "C2"].includes(p.zoning))
    .map((p) => {
      const served = popWithin(p, 2.2) * growth;
      const sPop = Math.min(100, (served / 12000) * 100);
      const sAcc = Math.max(0, 100 - p.roadAccessM / 3);
      const sLand = Math.min(100, (p.areaM2 / (req.minArea * 2)) * 100) * (1 - p.slopePct / 25);
      const sFlood = p.flood === "Low" ? 100 : p.flood === "Medium" ? 55 : 10;
      const nearest = existing.length ? Math.min(...existing.map((f) => km(p, f))) : 6;
      const sGap = Math.min(100, (nearest / 4) * 100);
      const sEnv = p.zoning === "G1" ? 35 : 80;
      const w = req.weights;
      const total =
        (sPop * w.Population + sAcc * w.Accessibility + sLand * w["Land suitability"] +
         sFlood * w["Flood risk"] + sGap * w["Existing coverage"] + sEnv * w.Environment) /
        Math.max(1, Object.values(w).reduce((a, b) => a + b, 0));
      return {
        entityId: p.id,
        score: Math.round(total * 10) / 10,
        label: "Parcel #" + p.id.split("_")[1] + " · " + p.ward,
        position: { lon: p.lon, lat: p.lat },
        breakdown: {
          Population: Math.round(sPop), Accessibility: Math.round(sAcc), "Land suitability": Math.round(sLand),
          "Flood risk": Math.round(sFlood), "Existing coverage": Math.round(sGap), Environment: Math.round(sEnv)
        },
        served: Math.round(served)
      };
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, 8);

  const top = scored[0];
  const metrics: Metric[] = [
    { key: "candidates", label: "Candidates evaluated", value: PARCELS.length },
    { key: "shortlist", label: "Shortlisted", value: scored.length },
    { key: "best", label: "Best score", value: top ? top.score : 0, unit: "/100", better: "up" },
    { key: "pop", label: "Population served", value: top ? (top as any).served.toLocaleString("en-IN") : 0 },
    { key: "travel", label: "Avg travel time", value: 22, unit: "min", delta: -9, better: "down" },
    { key: "cost", label: "Indicative cost", value: "₹" + (34 + Math.round(req.capacity / 12)) + " Cr" }
  ];

  return {
    resultId: uid("res"),
    type: "suitability",
    title: req.facility + " site suitability",
    datasetVersion: CITY.datasetVersion,
    scenarioVersion: scenario.id,
    createdAt: new Date().toISOString(),
    metrics,
    layers: [
      { id: "hospital_candidates", type: "points", label: req.facility + " candidates" },
      { id: "suitability_surface", type: "heatmap", label: "Suitability surface" }
    ],
    entities: scored,
    explanation:
      top
        ? "Top ranked site " + top.label + " scores " + top.score + "/100. It combines high catchment population (" +
          top.breakdown.Population + "/100) with low flood exposure (" + top.breakdown["Flood risk"] +
          "/100) and sits outside the 2.2 km catchment of existing " + req.facility.toLowerCase() +
          " capacity, closing the largest service gap in the pilot sector."
        : "No parcel satisfies the current constraints. Relax the minimum land area or the flood rule."
  };
}

export function runAccessibility(scenario: Scenario): AnalysisResult {
  const g = 1 + scenario.populationGrowthPct / 100;
  return {
    resultId: uid("res"), type: "accessibility", title: "Emergency accessibility (15 min)",
    datasetVersion: CITY.datasetVersion, scenarioVersion: scenario.id, createdAt: new Date().toISOString(),
    metrics: [
      { key: "cov", label: "Population within 15 min", value: Math.round(62 / g * 1.18), unit: "%", delta: 12, better: "up" },
      { key: "avg", label: "Average travel time", value: 26, unit: "min", delta: -5, better: "down" },
      { key: "worst", label: "Worst ward", value: "W-5C" },
      { key: "uncov", label: "Uncovered population", value: Math.round(CITY.population * 0.31).toLocaleString("en-IN") }
    ],
    layers: [{ id: "isochrones", type: "polygons", label: "15-min isochrones" }],
    entities: PARCELS.filter((p) => p.population > 640).slice(0, 6).map((p) => ({
      entityId: p.id, score: Math.round(40 + (p.population % 50)), label: "Gap cluster " + p.ward,
      position: { lon: p.lon, lat: p.lat }, breakdown: { Population: p.population, Access: 42 }
    })),
    explanation: "Coverage is limited by the single arterial crossing the river corridor; a second crossing raises 15-minute coverage by an estimated 12 points."
  };
}

export function runRisk(scenario: Scenario): AnalysisResult {
  const high = PARCELS.filter((p) => p.flood === "High");
  return {
    resultId: uid("res"), type: "risk", title: "Flood risk exposure",
    datasetVersion: CITY.datasetVersion, scenarioVersion: scenario.id, createdAt: new Date().toISOString(),
    metrics: [
      { key: "parcels", label: "Parcels at high risk", value: high.length },
      { key: "pop", label: "Population exposed", value: high.reduce((s, p) => s + p.population, 0).toLocaleString("en-IN") },
      { key: "assets", label: "Critical assets", value: 3 },
      { key: "loss", label: "Annualised loss", value: "₹18 Cr" }
    ],
    layers: [{ id: "flood_100y", type: "polygons", label: "100-year flood extent" }],
    entities: high.slice(0, 6).map((p) => ({
      entityId: p.id, score: 90, label: "High risk · " + p.ward,
      position: { lon: p.lon, lat: p.lat }, breakdown: { Depth: 1.4, Population: p.population }
    })),
    explanation: "High-risk parcels follow the river corridor. Any facility siting excludes these parcels under the current constraint set."
  };
}

export const SCENARIOS: Scenario[] = [
  { id: "scn_base", name: "Base 2026", status: "baseline", createdAt: "2026-01-12", horizon: 2026, populationGrowthPct: 0, changes: [] },
  {
    id: "scn_plan_a", name: "Plan A — North corridor", status: "draft", createdAt: "2026-06-02", horizon: 2040, populationGrowthPct: 34,
    changes: [
      { id: "c1", type: "population", label: "Population growth +34%", detail: "Horizon 2040, ward-level trend model" },
      { id: "c2", type: "facility", label: "Hospital · 250 beds", detail: "Parcel #1421" },
      { id: "c3", type: "road", label: "Arterial link 4.2 km", detail: "6 lanes · 60 km/h" }
    ]
  },
  {
    id: "scn_plan_b", name: "Plan B — East infill", status: "review", createdAt: "2026-06-19", horizon: 2040, populationGrowthPct: 34,
    changes: [
      { id: "c4", type: "population", label: "Population growth +34%", detail: "Horizon 2040" },
      { id: "c5", type: "facility", label: "Hospital · 180 beds", detail: "Parcel #1608" },
      { id: "c6", type: "zoning", label: "Rezone 12 parcels R2 → R3", detail: "East infill belt" }
    ]
  }
];

export const COMPARISON_ROWS = [
  { metric: "Population served", base: "62%", a: "89%", b: "85%", better: "a" },
  { metric: "Avg travel time", base: "31 min", a: "22 min", b: "24 min", better: "a" },
  { metric: "Flood exposure", base: "—", a: "Low", b: "Medium", better: "a" },
  { metric: "Land consumed", base: "—", a: "8,200 m²", b: "6,900 m²", better: "b" },
  { metric: "Connectivity", base: "—", a: "+18%", b: "+12%", better: "a" },
  { metric: "Estimated cost", base: "—", a: "₹42 Cr", b: "₹36 Cr", better: "b" },
  { metric: "Emergency access", base: "—", a: "+22%", b: "+14%", better: "a" }
];
