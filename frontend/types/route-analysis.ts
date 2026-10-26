/* ── Disaster-Aware Point-to-Point Route Analysis Domain Types ── */

export type StudyAreaId = "panvel_kalundre_osm" | "pilot_synthetic_grid";

export type DataMode = "live" | "demo";

export type ScenarioHazardType = "flood" | "fire" | "road_blockage" | "affected_zone";

export type HazardSeverityMode = "closed" | "penalized";

export type RouteCostMetric = "time" | "distance";

export type MapInteractionMode =
  | "navigate"
  | "pick_origin"
  | "pick_destination"
  | "draw_hazard_polygon"
  | "pick_hazard_center"
  | "toggle_road_segment";

export interface RouteWaypoint {
  lon: number;
  lat: number;
  label: string;
  source: "preset" | "map_click" | "landmark" | "coordinates";
}

export interface StudyAreaLandmark {
  id: string;
  name: string;
  category: string;
  lon: number;
  lat: number;
}

export interface StudyAreaDefinition {
  id: StudyAreaId;
  name: string;
  shortName: string;
  region: string;
  description: string;
  provenance: string;
  networkType: "real_osm_extract" | "synthetic_benchmark_grid" | "live_postgis";
  isSyntheticBenchmark: boolean;
  bounds: [number, number, number, number]; // [minLon, minLat, maxLon, maxLat]
  center: { lon: number; lat: number };
  cameraHeightM: number;
  defaultOrigin: RouteWaypoint;
  defaultDestination: RouteWaypoint;
}

export interface DisasterScenarioConfig {
  id: string;
  name: string;
  studyAreaId: StudyAreaId;
  type: ScenarioHazardType;
  description: string;
  active: boolean;
  isPreset: boolean;
  severityMode: HazardSeverityMode;
  penaltyMultiplier: number; // >= 1.0
  geometryKind: "polygon" | "circle" | "segments_only";
  polygon: [number, number][]; // [[lon, lat], ...]
  center: [number, number] | null; // [lon, lat]
  radiusM: number;
  affectedRoadIds: string[];
  slowedRoadIds: string[];
  updatedAt: string;
}

export interface RoadNetworkSegment {
  id: string;
  name: string;
  roadClass: string;
  oneway: boolean;
  bridge?: boolean;
  lanes: number;
  speedKmh: number;
  coordinates: [number, number][];
}

export interface WaterwayFeature {
  id: string;
  name: string;
  kind: "polygon" | "line";
  coordinates: [number, number][];
}

export interface StudyAreaBuilding {
  id: string;
  name?: string | null;
  floors: number;
  heightM: number;
  coordinates: [number, number][];
}

export interface LoadedStudyAreaDataset {
  studyAreaId: StudyAreaId;
  roads: RoadNetworkSegment[];
  waterways: WaterwayFeature[];
  landmarks: StudyAreaLandmark[];
  buildings: StudyAreaBuilding[];
  nodeCount: number;
  directedEdgeCount: number;
}

export interface AffectedNetworkPreview {
  closedEdgeCount: number;
  penalizedEdgeCount: number;
  closedRoadIds: string[];
  penalizedRoadIds: string[];
  closedRoadNames: string[];
  penalizedRoadNames: string[];
  closedLengthM: number;
  penalizedLengthM: number;
  closedSegments: [number, number][][];
  penalizedSegments: [number, number][][];
}

export interface ComputedRouteLeg {
  feasible: boolean;
  path: [number, number][]; // [[lon, lat], ...]
  distanceM: number | null;
  travelTimeS: number | null;
  segmentCount: number;
  affectedSegmentCount: number;
  affectedRoadIds: string[];
  affectedRoadNames: string[];
  roadSequence: string[];
  exposedDistanceM: number;
  snapOriginM: number;
  snapDestinationM: number;
}

export interface RouteComparisonMetrics {
  baselineFeasible: boolean;
  alternativeFeasible: boolean;
  routesIdentical: boolean;
  distanceDeltaM: number | null;
  distanceDeltaPct: number | null;
  timeDeltaS: number | null;
  timeDeltaPct: number | null;
  avoidedSegments: number | null;
  exposureReductionM: number | null;
  summary: string;
  assumptions: string[];
  limitations: string[];
  warnings: string[];
}

export interface RouteResultProvenance {
  dataMode: DataMode;
  executionEngine: "backend_networkx_dijkstra" | "local_dijkstra_ts";
  studyAreaId: StudyAreaId;
  studyAreaName: string;
  networkSourceLabel: string;
  algorithm: string;
  costMetric: RouteCostMetric;
  computedAtIso: string;
  inputSignature: string;
}

export interface RouteComparisonResult {
  baselineRoute: ComputedRouteLeg;
  hazardAwareRoute: ComputedRouteLeg;
  affectedNetwork: AffectedNetworkPreview;
  comparison: RouteComparisonMetrics;
  computationTimeMs: number;
  originUsed: RouteWaypoint;
  destinationUsed: RouteWaypoint;
  scenarioUsed: DisasterScenarioConfig;
  provenance: RouteResultProvenance;
}

export type WizardStepNumber = 1 | 2 | 3 | 4 | 5 | 6 | 7;
