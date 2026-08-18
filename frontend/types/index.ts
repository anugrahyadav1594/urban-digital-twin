/* ── Core domain types (mirror the backend contracts) ───────────────── */

export type CityInfo = {
  id: string;
  name: string;
  state: string;
  datasetVersion: string;
  crs: string;
  areaKm2: number;
  population: number;
  households: number;
  wards: number;
  updatedAt: string;
  center: { lon: number; lat: number };
};

export type LayerKind = "buildings" | "parcels" | "roads" | "highways" | "population" | "landuse" | "water" | "flood" | "facilities" | "candidates" | "proposals";

export type Layer = {
  id: LayerKind;
  name: string;
  group: "Base" | "Semantic" | "Risk" | "Planning";
  visible: boolean;
  opacity: number;
  color: string;
  count: number;
  legend?: { label: string; color: string }[];
};

export type FeatureKind = "parcel" | "building" | "road" | "facility" | "candidate" | "zone";

export type FeatureRecord = {
  id: string;
  kind: FeatureKind;
  name: string;
  position: { lon: number; lat: number };
  attributes: Record<string, string | number>;
  scenarioVersion?: string;
};

export type Scenario = {
  id: string;
  name: string;
  status: "baseline" | "draft" | "review" | "approved" | "reopened";
  createdAt: string;
  horizon: number;
  populationGrowthPct: number;
  description?: string;
  changes: ScenarioChange[];
};

export type ScenarioChange = {
  id: string;
  type: "facility" | "road" | "zoning" | "population";
  label: string;
  detail: string;
};

export type Metric = { key: string; label: string; value: number | string; unit?: string; delta?: number; better?: "up" | "down" };

export type ResultLayer = { id: string; type: "heatmap" | "points" | "polygons" | "lines"; label: string };

export type ResultEntity = { entityId: string; score: number; label: string; position: { lon: number; lat: number }; breakdown: Record<string, number> };

export type AnalysisResult = {
  resultId: string;
  type: "suitability" | "accessibility" | "impact" | "risk" | "optimization" | "road_proposal";
  title: string;
  datasetVersion: string;
  scenarioVersion: string;
  createdAt: string;
  metrics: Metric[];
  layers: ResultLayer[];
  entities: ResultEntity[];
  explanation: string;
  geometry?: any;
};

export type JobStage = { key: string; label: string; state: "pending" | "running" | "done" };

export type Job = {
  id: string;
  title: string;
  kind: string;
  progress: number;
  state: "queued" | "running" | "succeeded" | "failed";
  stages: JobStage[];
  startedAt: number;
  resultId?: string;
};

export type AgentStep = {
  id: string;
  agent: "Planner" | "GIS" | "Network" | "Risk" | "Optimization" | "Cost" | "Validator" | "Report";
  text: string;
  state: "running" | "done";
  tool?: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  steps?: AgentStep[];
  resultId?: string;
};

export type SuitabilityRequest = {
  facility: "Hospital" | "School" | "Fire Station" | "Water Treatment";
  capacity: number;
  minArea: number;
  maxTravelMin: number;
  floodRule: "Exclude High" | "Exclude High + Medium" | "Allow all";
  weights: Record<string, number>;
  // Advanced planner controls. The backend supported these all along; the
  // API simply never exposed them.
  maxSlope?: number | null;
  allowedZoning?: string[];
  minDistanceSameType?: number | null;
  serviceRadius?: number;
  useNetwork?: boolean;
  enforceMaxTravel?: boolean;
};
