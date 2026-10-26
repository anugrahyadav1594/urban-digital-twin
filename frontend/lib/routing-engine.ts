/* ── Deterministic Graph & Dijkstra Disaster-Aware Routing Engine ──
 *
 * Logical graph model:
 *  - Road intersections and segment vertices are directed graph nodes.
 *  - Crossing segments are planarized at interior intersection points.
 *  - Navigable road segments are directed edges weighted by geodesic length (m)
 *    and free-flow travel time (s) from road-class / OSM speed limits.
 *  - Baseline and hazard-aware routes run binary-heap Dijkstra on the identical
 *    origin node, destination node, and base graph G.
 */

import type {
  AffectedNetworkPreview,
  ComputedRouteLeg,
  DataMode,
  DisasterScenarioConfig,
  LoadedStudyAreaDataset,
  RoadNetworkSegment,
  RouteComparisonResult,
  RouteCostMetric,
  RouteWaypoint,
  StudyAreaDefinition,
  StudyAreaId,
  StudyAreaLandmark,
} from "../types/route-analysis.ts";

export const MAX_SNAP_DISTANCE_M = 2500;
export const WARN_SNAP_DISTANCE_M = 150;

export const ROAD_CLASS_SPEED_KMH: Record<string, number> = {
  motorway: 80,
  motorway_link: 50,
  trunk: 60,
  trunk_link: 45,
  primary: 50,
  primary_link: 40,
  arterial: 50,
  secondary: 40,
  secondary_link: 35,
  "sub-arterial": 40,
  tertiary: 35,
  tertiary_link: 30,
  collector: 32,
  residential: 25,
  local: 25,
  unclassified: 25,
  living_street: 18,
  service: 15,
};

/* ── Study Area Definitions ── */

export const STUDY_AREAS: Record<StudyAreaId, StudyAreaDefinition> = {
  panvel_kalundre_osm: {
    id: "panvel_kalundre_osm",
    name: "New Panvel — Kalundre River Corridor",
    shortName: "New Panvel (OSM)",
    region: "Navi Mumbai / NAINA Pilot Sector, Maharashtra, IN",
    description:
      "Authentic OpenStreetMap street and bridge network spanning West New Panvel, Adai Circle, Matheran Road, Sukapur Road, and the Kalundre River crossings.",
    provenance:
      "Bundled OpenStreetMap Overpass extract (279 connected ways, 2,219 road nodes) in Demo Mode; PostGIS roads table in Live Mode.",
    networkType: "real_osm_extract",
    isSyntheticBenchmark: false,
    bounds: [73.119009, 18.981874, 73.194157, 19.023736],
    center: { lon: 73.1285, lat: 18.9935 },
    cameraHeightM: 3400,
    defaultOrigin: {
      lon: 73.11907,
      lat: 18.99672,
      label: "New Panvel Fire Brigade (West)",
      source: "preset",
    },
    defaultDestination: {
      lon: 73.13008,
      lat: 18.98628,
      label: "Life Care Hospital (East of Kalundre River)",
      source: "preset",
    },
  },
  pilot_synthetic_grid: {
    id: "pilot_synthetic_grid",
    name: "Pilot Sector — Controlled Synthetic Benchmark Grid",
    shortName: "Synthetic Benchmark Grid",
    region: "Controlled 7×7 Analytical Testbed (Centred at 73.1405°E, 18.9972°N)",
    description:
      "Explicitly synthetic orthogonal 7×7 arterial/sub-arterial benchmark lattice with exact uniform block spacing for deterministic verification of shortest-path and detour behavior.",
    provenance:
      "Synthetic Benchmark Network (planarized 7×7 grid, 49 intersections, 84 bidirectional links) — for controlled algorithm testing only, not real-world streets.",
    networkType: "synthetic_benchmark_grid",
    isSyntheticBenchmark: true,
    bounds: [73.1275, 18.985, 73.1535, 19.0095],
    center: { lon: 73.1405, lat: 18.9972 },
    cameraHeightM: 3600,
    defaultOrigin: {
      lon: 73.1319,
      lat: 18.9891,
      label: "SW Benchmark Node (Av-2 / St-2)",
      source: "preset",
    },
    defaultDestination: {
      lon: 73.1491,
      lat: 19.0053,
      label: "NE Benchmark Node (Av-6 / St-6)",
      source: "preset",
    },
  },
};

/* ── Preconfigured Scenarios ── */

export function createPresetScenarios(): DisasterScenarioConfig[] {
  const ts = "2026-10-25T00:00:00.000Z";
  return [
    {
      id: "preset_kalundre_flood",
      name: "Demonstration Flood — Kalundre River Lower Bridge",
      studyAreaId: "panvel_kalundre_osm",
      type: "flood",
      description:
        "Simulated riverine flood inundation across the lower Kalundre River crossing (Tertiary Bridge #459498364 and low-lying approach roads). Affected segments are marked impassable.",
      active: true,
      isPreset: true,
      severityMode: "closed",
      penaltyMultiplier: 3.0,
      geometryKind: "polygon",
      polygon: [
        [73.1279, 18.9866],
        [73.1299, 18.9866],
        [73.1299, 18.9882],
        [73.1279, 18.9882],
      ],
      center: [73.1289, 18.9874],
      radiusM: 140,
      affectedRoadIds: ["osm_way_459498364"],
      slowedRoadIds: [],
      updatedAt: ts,
    },
    {
      id: "preset_adai_fire",
      name: "Adai Circle & Matheran Road Fire Cordon",
      studyAreaId: "panvel_kalundre_osm",
      type: "fire",
      description:
        "Simulated urban structure fire safety cordon (175 m radius) closing primary arterial approaches through Adai Circle Junction.",
      active: true,
      isPreset: true,
      severityMode: "closed",
      penaltyMultiplier: 3.0,
      geometryKind: "circle",
      polygon: [],
      center: [73.12664, 18.99947],
      radiusM: 175,
      affectedRoadIds: [],
      slowedRoadIds: [],
      updatedAt: ts,
    },
    {
      id: "preset_sukapur_penalty",
      name: "Kalundre Crossing Waterlogging Slowdown (4.0× Penalty)",
      studyAreaId: "panvel_kalundre_osm",
      type: "affected_zone",
      description:
        "Simulated surface waterlogging that keeps the lower Kalundre crossing passable at 4.0× normal traversal cost, illustrating cost-based trade-off routing versus hard closure.",
      active: true,
      isPreset: true,
      severityMode: "penalized",
      penaltyMultiplier: 4.0,
      geometryKind: "polygon",
      polygon: [
        [73.1279, 18.9866],
        [73.1299, 18.9866],
        [73.1299, 18.9882],
        [73.1279, 18.9882],
      ],
      center: [73.1289, 18.9874],
      radiusM: 140,
      affectedRoadIds: [],
      slowedRoadIds: [],
      updatedAt: ts,
    },
    {
      id: "preset_underpass_blockage",
      name: "Panvel Underpass & Lower Bridge Blockage",
      studyAreaId: "panvel_kalundre_osm",
      type: "road_blockage",
      description:
        "Explicit segment-level road closure on Panvel Underpass and Tertiary Bridge #459498364 without a broad polygon footprint.",
      active: true,
      isPreset: true,
      severityMode: "closed",
      penaltyMultiplier: 3.0,
      geometryKind: "segments_only",
      polygon: [],
      center: null,
      radiusM: 120,
      affectedRoadIds: ["osm_way_476003940", "osm_way_459498364"],
      slowedRoadIds: [],
      updatedAt: ts,
    },
    {
      id: "preset_river_severance",
      name: "Multi-Bridge Kalundre Flood Severance (Isolation Case)",
      studyAreaId: "panvel_kalundre_osm",
      type: "flood",
      description:
        "Wide simulated flood corridor closing all bridges across the Kalundre River channel in the sector, demonstrating honest 'No feasible route found' reporting when graph connectivity is severed.",
      active: true,
      isPreset: true,
      severityMode: "closed",
      penaltyMultiplier: 3.0,
      geometryKind: "polygon",
      polygon: [
        [73.1278, 18.9840],
        [73.1338, 18.9840],
        [73.1338, 19.0020],
        [73.1278, 19.0020],
      ],
      center: [73.1308, 18.9930],
      radiusM: 600,
      affectedRoadIds: [],
      slowedRoadIds: [],
      updatedAt: ts,
    },
    {
      id: "preset_baseline_control",
      name: "Control — No Active Hazard",
      studyAreaId: "panvel_kalundre_osm",
      type: "flood",
      description:
        "Control scenario with hazard simulation disabled. Baseline and hazard-aware routes must be identical with zero simulated exposure.",
      active: false,
      isPreset: true,
      severityMode: "closed",
      penaltyMultiplier: 3.0,
      geometryKind: "polygon",
      polygon: [],
      center: null,
      radiusM: 150,
      affectedRoadIds: [],
      slowedRoadIds: [],
      updatedAt: ts,
    },
    {
      id: "preset_grid_central_flood",
      name: "Benchmark Central Intersection Flood Zone",
      studyAreaId: "pilot_synthetic_grid",
      type: "flood",
      description:
        "Closes the central arterial crossroads (Av-4 / St-4) of the 7×7 synthetic benchmark lattice, forcing a perimeter arterial detour.",
      active: true,
      isPreset: true,
      severityMode: "closed",
      penaltyMultiplier: 3.0,
      geometryKind: "polygon",
      polygon: [
        [73.1365, 18.9940],
        [73.1445, 18.9940],
        [73.1445, 19.0005],
        [73.1365, 19.0005],
      ],
      center: [73.1405, 18.9972],
      radiusM: 380,
      affectedRoadIds: [],
      slowedRoadIds: [],
      updatedAt: ts,
    },
    {
      id: "preset_grid_penalty",
      name: "Benchmark Central Slowdown (3.0× Penalty)",
      studyAreaId: "pilot_synthetic_grid",
      type: "affected_zone",
      description:
        "Applies a 3.0× cost multiplier across the central benchmark crossroads without hard closure.",
      active: true,
      isPreset: true,
      severityMode: "penalized",
      penaltyMultiplier: 3.0,
      geometryKind: "circle",
      polygon: [],
      center: [73.1405, 18.9972],
      radiusM: 420,
      affectedRoadIds: [],
      slowedRoadIds: [],
      updatedAt: ts,
    },
  ];
}

/* ── Geodesic & Planar Geometry Utilities ── */

const EARTH_RADIUS_M = 6371008.8;

export function haversineDistanceM(
  a: [number, number],
  b: [number, number]
): number {
  const toRad = Math.PI / 180;
  const dLat = (b[1] - a[1]) * toRad;
  const dLon = (b[0] - a[0]) * toRad;
  const lat1 = a[1] * toRad;
  const lat2 = b[1] * toRad;
  const sinLat = Math.sin(dLat / 2);
  const sinLon = Math.sin(dLon / 2);
  const h =
    sinLat * sinLat + Math.cos(lat1) * Math.cos(lat2) * sinLon * sinLon;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)));
}

function toLocalMeters(
  pt: [number, number],
  refLat: number
): [number, number] {
  const cosLat = Math.cos((refLat * Math.PI) / 180);
  return [pt[0] * 111320 * cosLat, pt[1] * 110540];
}

export function pointToSegmentDistanceM(
  p: [number, number],
  a: [number, number],
  b: [number, number]
): number {
  const refLat = (a[1] + b[1] + p[1]) / 3;
  const [px, py] = toLocalMeters(p, refLat);
  const [ax, ay] = toLocalMeters(a, refLat);
  const [bx, by] = toLocalMeters(b, refLat);
  const dx = bx - ax;
  const dy = by - ay;
  const lenSq = dx * dx + dy * dy;
  if (lenSq <= 1e-9) {
    return Math.hypot(px - ax, py - ay);
  }
  const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / lenSq));
  const projX = ax + t * dx;
  const projY = ay + t * dy;
  return Math.hypot(px - projX, py - projY);
}

function ccw(
  a: [number, number],
  b: [number, number],
  c: [number, number]
): number {
  return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
}

function onSegment(
  a: [number, number],
  b: [number, number],
  p: [number, number]
): boolean {
  const eps = 1e-9;
  return (
    p[0] >= Math.min(a[0], b[0]) - eps &&
    p[0] <= Math.max(a[0], b[0]) + eps &&
    p[1] >= Math.min(a[1], b[1]) - eps &&
    p[1] <= Math.max(a[1], b[1]) + eps
  );
}

export function segmentsProperlyOrTouchIntersect(
  a1: [number, number],
  a2: [number, number],
  b1: [number, number],
  b2: [number, number]
): boolean {
  const d1 = ccw(a1, a2, b1);
  const d2 = ccw(a1, a2, b2);
  const d3 = ccw(b1, b2, a1);
  const d4 = ccw(b1, b2, a2);

  if (
    ((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) &&
    ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0))
  ) {
    return true;
  }
  const eps = 1e-11;
  if (Math.abs(d1) <= eps && onSegment(a1, a2, b1)) return true;
  if (Math.abs(d2) <= eps && onSegment(a1, a2, b2)) return true;
  if (Math.abs(d3) <= eps && onSegment(b1, b2, a1)) return true;
  if (Math.abs(d4) <= eps && onSegment(b1, b2, a2)) return true;
  return false;
}

export function pointInPolygon(
  pt: [number, number],
  ring: [number, number][]
): boolean {
  if (ring.length < 3) return false;
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0];
    const yi = ring[i][1];
    const xj = ring[j][0];
    const yj = ring[j][1];
    const intersect =
      yi > pt[1] !== yj > pt[1] &&
      pt[0] < ((xj - xi) * (pt[1] - yi)) / (yj - yi + 1e-18) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

export function segmentIntersectsPolygon(
  a: [number, number],
  b: [number, number],
  polygon: [number, number][]
): boolean {
  if (polygon.length < 3) return false;
  if (pointInPolygon(a, polygon) || pointInPolygon(b, polygon)) return true;
  const mid: [number, number] = [(a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5];
  if (pointInPolygon(mid, polygon)) return true;
  for (let i = 0; i < polygon.length; i++) {
    const p1 = polygon[i];
    const p2 = polygon[(i + 1) % polygon.length];
    if (segmentsProperlyOrTouchIntersect(a, b, p1, p2)) return true;
  }
  return false;
}

export function circleToPolygon(
  center: [number, number],
  radiusM: number,
  steps = 28
): [number, number][] {
  const cosLat = Math.cos((center[1] * Math.PI) / 180);
  const dLon = radiusM / (111320 * Math.max(0.1, cosLat));
  const dLat = radiusM / 110540;
  const pts: [number, number][] = [];
  for (let i = 0; i < steps; i++) {
    const theta = (2 * Math.PI * i) / steps;
    pts.push([
      Number((center[0] + Math.cos(theta) * dLon).toFixed(6)),
      Number((center[1] + Math.sin(theta) * dLat).toFixed(6)),
    ]);
  }
  return pts;
}

export function validateHazardPolygon(
  polygon: [number, number][]
): string | null {
  if (!Array.isArray(polygon) || polygon.length < 3) {
    return "Hazard polygon requires at least 3 vertices.";
  }
  const unique = new Set<string>();
  for (const pt of polygon) {
    if (
      !Array.isArray(pt) ||
      pt.length < 2 ||
      !Number.isFinite(pt[0]) ||
      !Number.isFinite(pt[1]) ||
      pt[0] < -180 ||
      pt[0] > 180 ||
      pt[1] < -90 ||
      pt[1] > 90
    ) {
      return "Hazard polygon contains invalid geographic coordinates.";
    }
    unique.add(`${pt[0].toFixed(6)},${pt[1].toFixed(6)}`);
  }
  if (unique.size < 3) {
    return "Hazard polygon must have at least 3 distinct vertices.";
  }
  // Signed shoelace area check
  let area2 = 0;
  for (let i = 0; i < polygon.length; i++) {
    const [x1, y1] = polygon[i];
    const [x2, y2] = polygon[(i + 1) % polygon.length];
    area2 += x1 * y2 - x2 * y1;
  }
  if (Math.abs(area2) < 1e-11) {
    return "Hazard polygon vertices are collinear (zero area).";
  }
  // Check non-adjacent edge self-intersection
  const n = polygon.length;
  for (let i = 0; i < n; i++) {
    const a1 = polygon[i];
    const a2 = polygon[(i + 1) % n];
    for (let j = i + 2; j < n; j++) {
      if (i === 0 && j === n - 1) continue;
      const b1 = polygon[j];
      const b2 = polygon[(j + 1) % n];
      if (segmentsProperlyOrTouchIntersect(a1, a2, b1, b2)) {
        return "Hazard polygon edges cross each other (self-intersecting polygon).";
      }
    }
  }
  return null;
}

/* ── Graph Data Structures ── */

export interface DirectedRoadEdge {
  edgeId: string;
  from: string;
  to: string;
  fromCoord: [number, number];
  toCoord: [number, number];
  roadId: string;
  roadName: string;
  roadClass: string;
  lengthM: number;
  speedKmh: number;
  baseTimeS: number;
}

export interface RoadGraph {
  nodes: Map<string, [number, number]>;
  adj: Map<string, DirectedRoadEdge[]>;
  edges: DirectedRoadEdge[];
  routableCore: Set<string>;
  roadNamesById: Map<string, string>;
}

function nodeKey(lon: number, lat: number): string {
  return `${lon.toFixed(6)},${lat.toFixed(6)}`;
}

function interiorIntersection(
  a1: [number, number],
  a2: [number, number],
  b1: [number, number],
  b2: [number, number]
): [number, number] | null {
  const dax = a2[0] - a1[0];
  const day = a2[1] - a1[1];
  const dbx = b2[0] - b1[0];
  const dby = b2[1] - b1[1];
  const denom = dax * dby - day * dbx;
  if (Math.abs(denom) < 1e-12) return null;
  const dx = b1[0] - a1[0];
  const dy = b1[1] - a1[1];
  const t = (dx * dby - dy * dbx) / denom;
  const u = (dx * day - dy * dax) / denom;
  const eps = 1e-6;
  if (t > -eps && t < 1 + eps && u > -eps && u < 1 + eps) {
    const tc = Math.max(0, Math.min(1, t));
    return [
      Number((a1[0] + tc * dax).toFixed(6)),
      Number((a1[1] + tc * day).toFixed(6)),
    ];
  }
  return null;
}

interface RawSubSegment {
  a: [number, number];
  b: [number, number];
  road: RoadNetworkSegment;
}

/**
 * Planarize crossing road segments and build a directed topological graph
 * with Tarjan strongly connected core identification.
 */
export function buildRoadGraph(roads: RoadNetworkSegment[]): RoadGraph {
  const rawSegs: RawSubSegment[] = [];
  const roadNamesById = new Map<string, string>();

  for (const r of roads) {
    roadNamesById.set(r.id, r.name || r.id);
    const coords = r.coordinates;
    if (!Array.isArray(coords) || coords.length < 2) continue;
    for (let i = 0; i < coords.length - 1; i++) {
      const a: [number, number] = [
        Number(coords[i][0].toFixed(6)),
        Number(coords[i][1].toFixed(6)),
      ];
      const b: [number, number] = [
        Number(coords[i + 1][0].toFixed(6)),
        Number(coords[i + 1][1].toFixed(6)),
      ];
      if (a[0] === b[0] && a[1] === b[1]) continue;
      rawSegs.push({ a, b, road: r });
    }
  }

  // Planarize interior crossings (handles synthetic grids & unsplit crossings)
  const splitPoints: [number, number][][] = rawSegs.map((s) => [s.a, s.b]);
  const bboxes = rawSegs.map((s) => [
    Math.min(s.a[0], s.b[0]),
    Math.min(s.a[1], s.b[1]),
    Math.max(s.a[0], s.b[0]),
    Math.max(s.a[1], s.b[1]),
  ]);

  for (let i = 0; i < rawSegs.length; i++) {
    const bi = bboxes[i];
    for (let j = i + 1; j < rawSegs.length; j++) {
      const bj = bboxes[j];
      if (
        bi[2] < bj[0] - 1e-7 ||
        bj[2] < bi[0] - 1e-7 ||
        bi[3] < bj[1] - 1e-7 ||
        bj[3] < bi[1] - 1e-7
      ) {
        continue;
      }
      const pt = interiorIntersection(
        rawSegs[i].a,
        rawSegs[i].b,
        rawSegs[j].a,
        rawSegs[j].b
      );
      if (pt) {
        splitPoints[i].push(pt);
        splitPoints[j].push(pt);
      }
    }
  }

  const nodes = new Map<string, [number, number]>();
  const adj = new Map<string, DirectedRoadEdge[]>();
  const edges: DirectedRoadEdge[] = [];
  let edgeSeq = 0;

  const ensureNode = (pt: [number, number]): string => {
    const k = nodeKey(pt[0], pt[1]);
    if (!nodes.has(k)) {
      nodes.set(k, pt);
      adj.set(k, []);
    }
    return k;
  };

  for (let i = 0; i < rawSegs.length; i++) {
    const { a, b, road } = rawSegs[i];
    const pts = splitPoints[i];
    const dx = b[0] - a[0];
    const dy = b[1] - a[1];
    const norm = dx * dx + dy * dy || 1;
    pts.sort(
      (p1, p2) =>
        ((p1[0] - a[0]) * dx + (p1[1] - a[1]) * dy) / norm -
        ((p2[0] - a[0]) * dx + (p2[1] - a[1]) * dy) / norm
    );

    const speedKmh =
      Number.isFinite(road.speedKmh) && road.speedKmh > 0
        ? road.speedKmh
        : ROAD_CLASS_SPEED_KMH[road.roadClass] ?? 25;
    if (speedKmh <= 0) {
      throw new Error(`Invalid non-positive speed (${speedKmh}) on road ${road.id}`);
    }
    const speedMps = speedKmh / 3.6;

    for (let k = 0; k < pts.length - 1; k++) {
      const p1 = pts[k];
      const p2 = pts[k + 1];
      const u = ensureNode(p1);
      const v = ensureNode(p2);
      if (u === v) continue;
      const lengthM = haversineDistanceM(p1, p2);
      if (!Number.isFinite(lengthM) || lengthM <= 0) continue;
      const baseTimeS = lengthM / speedMps;

      const fwd: DirectedRoadEdge = {
        edgeId: `e_${edgeSeq++}`,
        from: u,
        to: v,
        fromCoord: p1,
        toCoord: p2,
        roadId: road.id,
        roadName: road.name || road.id,
        roadClass: road.roadClass,
        lengthM,
        speedKmh,
        baseTimeS,
      };
      adj.get(u)!.push(fwd);
      edges.push(fwd);

      if (!road.oneway) {
        const rev: DirectedRoadEdge = {
          edgeId: `e_${edgeSeq++}`,
          from: v,
          to: u,
          fromCoord: p2,
          toCoord: p1,
          roadId: road.id,
          roadName: road.name || road.id,
          roadClass: road.roadClass,
          lengthM,
          speedKmh,
          baseTimeS,
        };
        adj.get(v)!.push(rev);
        edges.push(rev);
      }
    }
  }

  const routableCore = computeLargestSCC(nodes, adj);
  return { nodes, adj, edges, routableCore, roadNamesById };
}

/** Iterative Tarjan Strongly Connected Components to avoid call-stack limits. */
function computeLargestSCC(
  nodes: Map<string, [number, number]>,
  adj: Map<string, DirectedRoadEdge[]>
): Set<string> {
  let index = 0;
  const indices = new Map<string, number>();
  const lowlink = new Map<string, number>();
  const onStack = new Set<string>();
  const stack: string[] = [];
  let largest = new Set<string>();

  for (const startNode of nodes.keys()) {
    if (indices.has(startNode)) continue;

    const callStack: { node: string; edgeIdx: number }[] = [
      { node: startNode, edgeIdx: 0 },
    ];
    indices.set(startNode, index);
    lowlink.set(startNode, index);
    index++;
    stack.push(startNode);
    onStack.add(startNode);

    while (callStack.length > 0) {
      const frame = callStack[callStack.length - 1];
      const outEdges = adj.get(frame.node) ?? [];
      if (frame.edgeIdx < outEdges.length) {
        const w = outEdges[frame.edgeIdx].to;
        frame.edgeIdx++;
        if (!indices.has(w)) {
          indices.set(w, index);
          lowlink.set(w, index);
          index++;
          stack.push(w);
          onStack.add(w);
          callStack.push({ node: w, edgeIdx: 0 });
        } else if (onStack.has(w)) {
          lowlink.set(
            frame.node,
            Math.min(lowlink.get(frame.node)!, indices.get(w)!)
          );
        }
      } else {
        callStack.pop();
        if (callStack.length > 0) {
          const parent = callStack[callStack.length - 1].node;
          lowlink.set(
            parent,
            Math.min(lowlink.get(parent)!, lowlink.get(frame.node)!)
          );
        }
        if (lowlink.get(frame.node) === indices.get(frame.node)) {
          const comp = new Set<string>();
          while (stack.length > 0) {
            const w = stack.pop()!;
            onStack.delete(w);
            comp.add(w);
            if (w === frame.node) break;
          }
          if (comp.size > largest.size) {
            largest = comp;
          }
        }
      }
    }
  }
  return largest;
}

/* ── Hazard Classification on Graph ── */

export interface ClassifiedEdges {
  closedEdgeIds: Set<string>;
  penalizedEdgeIds: Set<string>;
  preview: AffectedNetworkPreview;
}

export function classifyScenarioOnGraph(
  graph: RoadGraph,
  scenario: DisasterScenarioConfig
): ClassifiedEdges {
  if (
    !Number.isFinite(scenario.penaltyMultiplier) ||
    scenario.penaltyMultiplier < 1.0
  ) {
    throw new Error(
      `Invalid penalty multiplier (${scenario.penaltyMultiplier}); expected a finite number >= 1.0.`
    );
  }

  const closedEdgeIds = new Set<string>();
  const penalizedEdgeIds = new Set<string>();
  const closedRoadIds = new Set<string>();
  const penalizedRoadIds = new Set<string>();
  const closedSegments: [number, number][][] = [];
  const penalizedSegments: [number, number][][] = [];
  const seenSegKey = new Set<string>();
  let closedLengthM = 0;
  let penalizedLengthM = 0;

  if (!scenario.active) {
    return {
      closedEdgeIds,
      penalizedEdgeIds,
      preview: {
        closedEdgeCount: 0,
        penalizedEdgeCount: 0,
        closedRoadIds: [],
        penalizedRoadIds: [],
        closedRoadNames: [],
        penalizedRoadNames: [],
        closedLengthM: 0,
        penalizedLengthM: 0,
        closedSegments: [],
        penalizedSegments: [],
      },
    };
  }

  if (scenario.geometryKind === "polygon" && scenario.polygon.length > 0) {
    const polyErr = validateHazardPolygon(scenario.polygon);
    if (polyErr) {
      throw new Error(polyErr);
    }
  }
  if (
    scenario.geometryKind === "circle" &&
    scenario.center &&
    (!Number.isFinite(scenario.radiusM) || scenario.radiusM <= 0)
  ) {
    throw new Error("Hazard radius must be greater than 0 metres.");
  }

  const explicitAffected = new Set(scenario.affectedRoadIds);
  const explicitSlowed = new Set(scenario.slowedRoadIds);

  for (const edge of graph.edges) {
    const inExplicit = explicitAffected.has(edge.roadId);
    const inSlowed = explicitSlowed.has(edge.roadId);
    let inGeometry = false;

    if (scenario.geometryKind === "polygon" && scenario.polygon.length >= 3) {
      inGeometry = segmentIntersectsPolygon(
        edge.fromCoord,
        edge.toCoord,
        scenario.polygon
      );
    } else if (
      scenario.geometryKind === "circle" &&
      scenario.center &&
      scenario.radiusM > 0
    ) {
      const d = pointToSegmentDistanceM(
        scenario.center,
        edge.fromCoord,
        edge.toCoord
      );
      inGeometry = d <= scenario.radiusM;
    }

    const undirectedKey =
      edge.from < edge.to
        ? `${edge.from}|${edge.to}`
        : `${edge.to}|${edge.from}`;

    if (inExplicit || inGeometry) {
      if (scenario.severityMode === "closed") {
        closedEdgeIds.add(edge.edgeId);
        closedRoadIds.add(edge.roadId);
        if (!seenSegKey.has(`c:${undirectedKey}`)) {
          seenSegKey.add(`c:${undirectedKey}`);
          closedLengthM += edge.lengthM;
          closedSegments.push([edge.fromCoord, edge.toCoord]);
        }
      } else {
        penalizedEdgeIds.add(edge.edgeId);
        penalizedRoadIds.add(edge.roadId);
        if (!seenSegKey.has(`p:${undirectedKey}`)) {
          seenSegKey.add(`p:${undirectedKey}`);
          penalizedLengthM += edge.lengthM;
          penalizedSegments.push([edge.fromCoord, edge.toCoord]);
        }
      }
    } else if (inSlowed) {
      penalizedEdgeIds.add(edge.edgeId);
      penalizedRoadIds.add(edge.roadId);
      if (!seenSegKey.has(`p:${undirectedKey}`)) {
        seenSegKey.add(`p:${undirectedKey}`);
        penalizedLengthM += edge.lengthM;
        penalizedSegments.push([edge.fromCoord, edge.toCoord]);
      }
    }
  }

  const closedIdsArr = Array.from(closedRoadIds);
  const penIdsArr = Array.from(penalizedRoadIds);

  return {
    closedEdgeIds,
    penalizedEdgeIds,
    preview: {
      closedEdgeCount: closedEdgeIds.size,
      penalizedEdgeCount: penalizedEdgeIds.size,
      closedRoadIds: closedIdsArr,
      penalizedRoadIds: penIdsArr,
      closedRoadNames: Array.from(
        new Set(closedIdsArr.map((id) => graph.roadNamesById.get(id) ?? id))
      ),
      penalizedRoadNames: Array.from(
        new Set(penIdsArr.map((id) => graph.roadNamesById.get(id) ?? id))
      ),
      closedLengthM: Math.round(closedLengthM),
      penalizedLengthM: Math.round(penalizedLengthM),
      closedSegments,
      penalizedSegments,
    },
  };
}

/* ── Binary Min-Heap & Dijkstra Shortest Path ── */

class MinHeap {
  private items: { node: string; cost: number }[] = [];

  get size(): number {
    return this.items.length;
  }

  push(node: string, cost: number): void {
    this.items.push({ node, cost });
    this.bubbleUp(this.items.length - 1);
  }

  pop(): { node: string; cost: number } | undefined {
    if (this.items.length === 0) return undefined;
    const top = this.items[0];
    const last = this.items.pop()!;
    if (this.items.length > 0) {
      this.items[0] = last;
      this.sinkDown(0);
    }
    return top;
  }

  private bubbleUp(idx: number): void {
    while (idx > 0) {
      const parent = (idx - 1) >> 1;
      if (this.items[parent].cost <= this.items[idx].cost) break;
      const tmp = this.items[parent];
      this.items[parent] = this.items[idx];
      this.items[idx] = tmp;
      idx = parent;
    }
  }

  private sinkDown(idx: number): void {
    const n = this.items.length;
    while (true) {
      let smallest = idx;
      const left = idx * 2 + 1;
      const right = idx * 2 + 2;
      if (left < n && this.items[left].cost < this.items[smallest].cost) {
        smallest = left;
      }
      if (right < n && this.items[right].cost < this.items[smallest].cost) {
        smallest = right;
      }
      if (smallest === idx) break;
      const tmp = this.items[smallest];
      this.items[smallest] = this.items[idx];
      this.items[idx] = tmp;
      idx = smallest;
    }
  }
}

export function snapPointToGraph(
  graph: RoadGraph,
  lon: number,
  lat: number
): { nodeKey: string; coord: [number, number]; distanceM: number } | null {
  const candidates =
    graph.routableCore.size > 0
      ? graph.routableCore
      : new Set(graph.nodes.keys());
  let bestKey: string | null = null;
  let bestCoord: [number, number] | null = null;
  let bestDist = Infinity;

  for (const key of candidates) {
    const coord = graph.nodes.get(key)!;
    const d = haversineDistanceM([lon, lat], coord);
    if (d < bestDist) {
      bestDist = d;
      bestKey = key;
      bestCoord = coord;
    }
  }
  if (!bestKey || !bestCoord) return null;
  return { nodeKey: bestKey, coord: bestCoord, distanceM: bestDist };
}

export function dijkstraShortestPath(
  graph: RoadGraph,
  startNode: string,
  goalNode: string,
  options: {
    costMetric: RouteCostMetric;
    closedEdgeIds?: Set<string>;
    penalizedEdgeIds?: Set<string>;
    penaltyMultiplier?: number;
  }
): DirectedRoadEdge[] | null {
  const {
    costMetric,
    closedEdgeIds = new Set(),
    penalizedEdgeIds = new Set(),
    penaltyMultiplier = 1.0,
  } = options;

  if (!Number.isFinite(penaltyMultiplier) || penaltyMultiplier < 1.0) {
    throw new Error("Penalty multiplier must be >= 1.0");
  }

  const dist = new Map<string, number>();
  const prevEdge = new Map<string, DirectedRoadEdge>();
  const heap = new MinHeap();

  dist.set(startNode, 0);
  heap.push(startNode, 0);

  while (heap.size > 0) {
    const cur = heap.pop()!;
    if (cur.cost > (dist.get(cur.node) ?? Infinity)) continue;
    if (cur.node === goalNode) break;

    const outgoing = graph.adj.get(cur.node) ?? [];
    for (const edge of outgoing) {
      if (closedEdgeIds.has(edge.edgeId)) continue;
      const baseCost =
        costMetric === "time" ? edge.baseTimeS : edge.lengthM;
      if (!Number.isFinite(baseCost) || baseCost <= 0) {
        throw new Error(`Invalid non-positive edge cost on ${edge.edgeId}`);
      }
      const mult = penalizedEdgeIds.has(edge.edgeId) ? penaltyMultiplier : 1.0;
      const nextCost = cur.cost + baseCost * mult;
      if (nextCost < (dist.get(edge.to) ?? Infinity)) {
        dist.set(edge.to, nextCost);
        prevEdge.set(edge.to, edge);
        heap.push(edge.to, nextCost);
      }
    }
  }

  if (!prevEdge.has(goalNode) && startNode !== goalNode) {
    return null;
  }

  const edgePath: DirectedRoadEdge[] = [];
  let cursor = goalNode;
  while (cursor !== startNode) {
    const e = prevEdge.get(cursor);
    if (!e) return null;
    edgePath.push(e);
    cursor = e.from;
  }
  edgePath.reverse();
  return edgePath;
}

function summarizeEdgePath(
  edgesUsed: DirectedRoadEdge[] | null,
  allAffectedEdgeIds: Set<string>,
  snapOriginM: number,
  snapDestM: number
): ComputedRouteLeg {
  if (!edgesUsed) {
    return {
      feasible: false,
      path: [],
      distanceM: null,
      travelTimeS: null,
      segmentCount: 0,
      affectedSegmentCount: 0,
      affectedRoadIds: [],
      affectedRoadNames: [],
      roadSequence: [],
      exposedDistanceM: 0,
      snapOriginM: Number(snapOriginM.toFixed(1)),
      snapDestinationM: Number(snapDestM.toFixed(1)),
    };
  }

  const coords: [number, number][] =
    edgesUsed.length > 0 ? [edgesUsed[0].fromCoord] : [];
  let totalDist = 0;
  let totalTime = 0;
  let affectedSegs = 0;
  let exposedDist = 0;
  const affectedRoadIds = new Set<string>();
  const affectedRoadNames = new Set<string>();
  const roadSequence: string[] = [];

  for (const e of edgesUsed) {
    coords.push(e.toCoord);
    totalDist += e.lengthM;
    totalTime += e.baseTimeS;
    if (
      roadSequence.length === 0 ||
      roadSequence[roadSequence.length - 1] !== e.roadName
    ) {
      roadSequence.push(e.roadName);
    }
    if (allAffectedEdgeIds.has(e.edgeId)) {
      affectedSegs++;
      exposedDist += e.lengthM;
      affectedRoadIds.add(e.roadId);
      affectedRoadNames.add(e.roadName);
    }
  }

  return {
    feasible: true,
    path: coords,
    distanceM: Number(totalDist.toFixed(1)),
    travelTimeS: Number(totalTime.toFixed(1)),
    segmentCount: edgesUsed.length,
    affectedSegmentCount: affectedSegs,
    affectedRoadIds: Array.from(affectedRoadIds),
    affectedRoadNames: Array.from(affectedRoadNames),
    roadSequence,
    exposedDistanceM: Number(exposedDist.toFixed(1)),
    snapOriginM: Number(snapOriginM.toFixed(1)),
    snapDestinationM: Number(snapDestM.toFixed(1)),
  };
}

export function computeInputSignature(params: {
  studyAreaId: StudyAreaId;
  origin: RouteWaypoint | null;
  destination: RouteWaypoint | null;
  scenario: DisasterScenarioConfig;
  costMetric: RouteCostMetric;
  dataMode: DataMode;
}): string {
  const { studyAreaId, origin, destination, scenario, costMetric, dataMode } =
    params;
  if (!origin || !destination) return "incomplete";
  return JSON.stringify({
    studyAreaId,
    dataMode,
    costMetric,
    o: [Number(origin.lon.toFixed(5)), Number(origin.lat.toFixed(5))],
    d: [Number(destination.lon.toFixed(5)), Number(destination.lat.toFixed(5))],
    s: {
      id: scenario.id,
      type: scenario.type,
      active: scenario.active,
      severityMode: scenario.severityMode,
      penaltyMultiplier: Number(scenario.penaltyMultiplier.toFixed(2)),
      geometryKind: scenario.geometryKind,
      polygon: scenario.polygon.map((p) => [
        Number(p[0].toFixed(5)),
        Number(p[1].toFixed(5)),
      ]),
      center: scenario.center
        ? [
            Number(scenario.center[0].toFixed(5)),
            Number(scenario.center[1].toFixed(5)),
          ]
        : null,
      radiusM: Math.round(scenario.radiusM),
      affectedRoadIds: [...scenario.affectedRoadIds].sort(),
      slowedRoadIds: [...scenario.slowedRoadIds].sort(),
    },
  });
}

/* ── Full Local Route Comparison ── */

export function compareRoutesOnGraph(params: {
  graph: RoadGraph;
  studyArea: StudyAreaDefinition;
  origin: RouteWaypoint;
  destination: RouteWaypoint;
  scenario: DisasterScenarioConfig;
  costMetric: RouteCostMetric;
  dataMode: DataMode;
}): RouteComparisonResult {
  const t0 = typeof performance !== "undefined" ? performance.now() : Date.now();
  const { graph, studyArea, origin, destination, scenario, costMetric, dataMode } =
    params;

  if (
    !origin ||
    !Number.isFinite(origin.lon) ||
    !Number.isFinite(origin.lat) ||
    Math.abs(origin.lon) > 180 ||
    Math.abs(origin.lat) > 90
  ) {
    throw new Error("Origin coordinates are missing or invalid.");
  }
  if (
    !destination ||
    !Number.isFinite(destination.lon) ||
    !Number.isFinite(destination.lat) ||
    Math.abs(destination.lon) > 180 ||
    Math.abs(destination.lat) > 90
  ) {
    throw new Error("Destination coordinates are missing or invalid.");
  }
  if (graph.nodes.size === 0 || graph.edges.length === 0) {
    throw new Error("Selected study area road graph is empty.");
  }

  const snapO = snapPointToGraph(graph, origin.lon, origin.lat);
  const snapD = snapPointToGraph(graph, destination.lon, destination.lat);
  if (!snapO || !snapD) {
    throw new Error("Could not snap origin or destination onto a connected road.");
  }
  if (snapO.distanceM > MAX_SNAP_DISTANCE_M) {
    throw new Error(
      `Origin is ${Math.round(snapO.distanceM)} m outside the navigable road network (max ${MAX_SNAP_DISTANCE_M} m).`
    );
  }
  if (snapD.distanceM > MAX_SNAP_DISTANCE_M) {
    throw new Error(
      `Destination is ${Math.round(snapD.distanceM)} m outside the navigable road network (max ${MAX_SNAP_DISTANCE_M} m).`
    );
  }
  if (snapO.nodeKey === snapD.nodeKey) {
    throw new Error(
      "Origin and destination map to the same road intersection. Choose two distinct locations."
    );
  }

  const classified = classifyScenarioOnGraph(graph, scenario);
  const allAffectedEdges = new Set<string>([
    ...classified.closedEdgeIds,
    ...classified.penalizedEdgeIds,
  ]);

  const baseEdges = dijkstraShortestPath(
    graph,
    snapO.nodeKey,
    snapD.nodeKey,
    { costMetric }
  );

  const altEdges = dijkstraShortestPath(
    graph,
    snapO.nodeKey,
    snapD.nodeKey,
    {
      costMetric,
      closedEdgeIds: classified.closedEdgeIds,
      penalizedEdgeIds: classified.penalizedEdgeIds,
      penaltyMultiplier: scenario.penaltyMultiplier,
    }
  );

  const baselineRoute = summarizeEdgePath(
    baseEdges,
    allAffectedEdges,
    snapO.distanceM,
    snapD.distanceM
  );
  const hazardAwareRoute = summarizeEdgePath(
    altEdges,
    allAffectedEdges,
    snapO.distanceM,
    snapD.distanceM
  );

  const t1 = typeof performance !== "undefined" ? performance.now() : Date.now();
  const computationTimeMs = Math.max(0.1, Number((t1 - t0).toFixed(2)));

  const routesIdentical = Boolean(
    baseEdges &&
      altEdges &&
      baseEdges.length === altEdges.length &&
      baseEdges.every((e, idx) => e.edgeId === altEdges[idx].edgeId)
  );

  let distanceDeltaM: number | null = null;
  let distanceDeltaPct: number | null = null;
  let timeDeltaS: number | null = null;
  let timeDeltaPct: number | null = null;
  let avoidedSegments: number | null = null;
  let exposureReductionM: number | null = null;

  if (
    baselineRoute.feasible &&
    hazardAwareRoute.feasible &&
    baselineRoute.distanceM !== null &&
    hazardAwareRoute.distanceM !== null &&
    baselineRoute.travelTimeS !== null &&
    hazardAwareRoute.travelTimeS !== null
  ) {
    distanceDeltaM = Number(
      (hazardAwareRoute.distanceM - baselineRoute.distanceM).toFixed(1)
    );
    distanceDeltaPct =
      baselineRoute.distanceM > 0
        ? Number(((distanceDeltaM / baselineRoute.distanceM) * 100).toFixed(1))
        : 0;
    timeDeltaS = Number(
      (hazardAwareRoute.travelTimeS - baselineRoute.travelTimeS).toFixed(1)
    );
    timeDeltaPct =
      baselineRoute.travelTimeS > 0
        ? Number(((timeDeltaS / baselineRoute.travelTimeS) * 100).toFixed(1))
        : 0;
    avoidedSegments =
      baselineRoute.affectedSegmentCount - hazardAwareRoute.affectedSegmentCount;
    exposureReductionM = Number(
      (
        baselineRoute.exposedDistanceM - hazardAwareRoute.exposedDistanceM
      ).toFixed(1)
    );
  }

  const warnings: string[] = [];
  if (snapO.distanceM > WARN_SNAP_DISTANCE_M) {
    warnings.push(
      `Origin was snapped ${Math.round(snapO.distanceM)} m to the nearest connected road intersection.`
    );
  }
  if (snapD.distanceM > WARN_SNAP_DISTANCE_M) {
    warnings.push(
      `Destination was snapped ${Math.round(snapD.distanceM)} m to the nearest connected road intersection.`
    );
  }
  if (scenario.active && allAffectedEdges.size === 0) {
    warnings.push(
      "Active hazard scenario does not intersect any navigable road segments in this study area."
    );
  }

  const summary = buildPlainEnglishSummary({
    scenario,
    baselineRoute,
    hazardAwareRoute,
    routesIdentical,
    distanceDeltaM,
    timeDeltaS,
    closedCount: classified.preview.closedEdgeCount,
    penalizedCount: classified.preview.penalizedEdgeCount,
  });

  const assumptions = [
    `Shortest paths computed with Dijkstra's algorithm minimizing ${
      costMetric === "time" ? "nominal road-class travel time" : "geodesic network distance"
    } on identical origin/destination nodes.`,
    "Nominal travel time uses OSM maxspeed tags where available, otherwise standard speed-by-road-class defaults (primary 50, secondary 40, tertiary 35, residential 25 km/h), without live traffic or intersection signal delay.",
    scenario.severityMode === "closed"
      ? "Impassable mode: graph edges intersecting the simulated hazard or explicitly marked closed are excluded from the hazard-aware graph."
      : `Penalized mode: affected graph edges remain traversable at ${scenario.penaltyMultiplier.toFixed(1)}× baseline traversal cost.`,
    "Affected-segment exposure equals the cumulative length (m) of traversed graph edges belonging to the simulated hazard set.",
  ];

  const limitations = [
    studyArea.isSyntheticBenchmark
      ? "Routes are computed on a controlled synthetic 7×7 benchmark lattice designed for algorithm verification, not real streets."
      : "Demo Mode uses a static OpenStreetMap extract; private alleys, informal footpaths, and unmapped local barriers are not represented.",
    "Hazard footprints represent user-configured or preset simulation zones, not live sensor telemetry or physical flood-depth / fire-propagation simulations.",
    "A feasible hazard-aware route indicates graph connectivity outside closed segments; it must not be interpreted as a guarantee of real-world life safety.",
  ];

  return {
    baselineRoute,
    hazardAwareRoute,
    affectedNetwork: classified.preview,
    comparison: {
      baselineFeasible: baselineRoute.feasible,
      alternativeFeasible: hazardAwareRoute.feasible,
      routesIdentical,
      distanceDeltaM,
      distanceDeltaPct,
      timeDeltaS,
      timeDeltaPct,
      avoidedSegments,
      exposureReductionM,
      summary,
      assumptions,
      limitations,
      warnings,
    },
    computationTimeMs,
    originUsed: origin,
    destinationUsed: destination,
    scenarioUsed: structuredClone(scenario),
    provenance: {
      dataMode,
      executionEngine: "local_dijkstra_ts",
      studyAreaId: studyArea.id,
      studyAreaName: studyArea.name,
      networkSourceLabel: studyArea.isSyntheticBenchmark
        ? "Controlled Synthetic 7×7 Benchmark Grid"
        : "Offline OpenStreetMap Extract (New Panvel / Kalundre Corridor)",
      algorithm: "Dijkstra Shortest Path (Binary Heap)",
      costMetric,
      computedAtIso: new Date().toISOString(),
      inputSignature: computeInputSignature({
        studyAreaId: studyArea.id,
        origin,
        destination,
        scenario,
        costMetric,
        dataMode,
      }),
    },
  };
}

function buildPlainEnglishSummary(args: {
  scenario: DisasterScenarioConfig;
  baselineRoute: ComputedRouteLeg;
  hazardAwareRoute: ComputedRouteLeg;
  routesIdentical: boolean;
  distanceDeltaM: number | null;
  timeDeltaS: number | null;
  closedCount: number;
  penalizedCount: number;
}): string {
  const {
    scenario,
    baselineRoute,
    hazardAwareRoute,
    routesIdentical,
    distanceDeltaM,
    timeDeltaS,
    closedCount,
    penalizedCount,
  } = args;

  if (!baselineRoute.feasible || baselineRoute.distanceM === null) {
    return "No feasible baseline route exists between the selected origin and destination on this road network.";
  }

  const baseKm = (baselineRoute.distanceM / 1000).toFixed(2);
  const baseMin = ((baselineRoute.travelTimeS ?? 0) / 60).toFixed(1);

  if (!scenario.active) {
    return `Scenario "${scenario.name}" is inactive. Both baseline and hazard-aware calculations follow the same ${baseKm} km (${baseMin} min) route with 0 m simulated exposure.`;
  }

  if (!hazardAwareRoute.feasible || hazardAwareRoute.distanceM === null) {
    return `No feasible route found under the current scenario ("${scenario.name}"). The baseline route (${baseKm} km) traverses ${baselineRoute.affectedSegmentCount} affected segment(s) (${Math.round(baselineRoute.exposedDistanceM)} m simulated exposure), and excluding the ${closedCount} impassable directed edge(s) disconnects all navigable paths between origin and destination.`;
  }

  if (routesIdentical) {
    if (baselineRoute.affectedSegmentCount === 0) {
      return `The baseline route (${baseKm} km, ${baseMin} min) already avoids all ${closedCount + penalizedCount} directed edge(s) affected by "${scenario.name}", so no detour is required.`;
    }
    return `Under ${scenario.penaltyMultiplier.toFixed(1)}× traversal penalty mode, the baseline route (${baseKm} km, ${baseMin} min) remains lower-cost than any available detour, retaining ${Math.round(baselineRoute.exposedDistanceM)} m of simulated exposure across ${baselineRoute.affectedSegmentCount} segment(s).`;
  }

  const altKm = (hazardAwareRoute.distanceM / 1000).toFixed(2);
  const altMin = ((hazardAwareRoute.travelTimeS ?? 0) / 60).toFixed(1);
  const dKm = ((distanceDeltaM ?? 0) / 1000).toFixed(2);
  const dMin = ((timeDeltaS ?? 0) / 60).toFixed(1);
  const signKm = (distanceDeltaM ?? 0) >= 0 ? "+" : "";
  const signMin = (timeDeltaS ?? 0) >= 0 ? "+" : "";
  const hitStreets =
    baselineRoute.affectedRoadNames.length > 0
      ? ` (${baselineRoute.affectedRoadNames.slice(0, 2).join(", ")})`
      : "";

  return `The baseline route (${baseKm} km, ${baseMin} min) traverses ${baselineRoute.affectedSegmentCount} simulated hazard-affected segment(s)${hitStreets} (${Math.round(baselineRoute.exposedDistanceM)} m simulated exposure). Under "${scenario.name}", the hazard-aware alternative reroutes to ${altKm} km (${altMin} min; ${signKm}${dKm} km, ${signMin}${dMin} min), reducing simulated affected-segment exposure from ${Math.round(baselineRoute.exposedDistanceM)} m to ${Math.round(hazardAwareRoute.exposedDistanceM)} m.`;
}

/* ── Synthetic Benchmark Grid Dataset Builder ── */

export function buildSyntheticBenchmarkDataset(): LoadedStudyAreaDataset {
  const originLon = 73.1405 - 0.013;
  const originLat = 18.9972 - 0.012;
  const stepLon = 0.026 / 6;
  const stepLat = 0.024 / 6;

  const roads: RoadNetworkSegment[] = [];
  for (let i = 0; i <= 6; i++) {
    const lon = Number((originLon + i * stepLon).toFixed(6));
    const lat = Number((originLat + i * stepLat).toFixed(6));
    const isArterial = i === 0 || i === 3 || i === 6;

    roads.push({
      id: `grid_av_${i + 1}`,
      name: `Benchmark Avenue ${i + 1}${isArterial ? " (Arterial)" : ""}`,
      roadClass: isArterial ? "arterial" : "sub-arterial",
      oneway: false,
      bridge: i === 3,
      lanes: isArterial ? 4 : 2,
      speedKmh: isArterial ? 50 : 35,
      coordinates: [
        [lon, Number(originLat.toFixed(6))],
        [lon, Number((originLat + 6 * stepLat).toFixed(6))],
      ],
    });

    roads.push({
      id: `grid_st_${i + 1}`,
      name: `Benchmark Street ${i + 1}${isArterial ? " (Arterial)" : ""}`,
      roadClass: isArterial ? "arterial" : "sub-arterial",
      oneway: false,
      bridge: false,
      lanes: isArterial ? 4 : 2,
      speedKmh: isArterial ? 50 : 35,
      coordinates: [
        [Number(originLon.toFixed(6)), lat],
        [Number((originLon + 6 * stepLon).toFixed(6)), lat],
      ],
    });
  }

  const landmarks: StudyAreaLandmark[] = [
    {
      id: "grid_sw",
      name: "SW Benchmark Node (Av-2 / St-2)",
      category: "junction",
      lon: Number((originLon + 1 * stepLon).toFixed(6)),
      lat: Number((originLat + 1 * stepLat).toFixed(6)),
    },
    {
      id: "grid_center",
      name: "Central Benchmark Crossroads (Av-4 / St-4)",
      category: "junction",
      lon: Number((originLon + 3 * stepLon).toFixed(6)),
      lat: Number((originLat + 3 * stepLat).toFixed(6)),
    },
    {
      id: "grid_ne",
      name: "NE Benchmark Node (Av-6 / St-6)",
      category: "junction",
      lon: Number((originLon + 5 * stepLon).toFixed(6)),
      lat: Number((originLat + 5 * stepLat).toFixed(6)),
    },
    {
      id: "grid_nw",
      name: "NW Perimeter Node (Av-1 / St-7)",
      category: "junction",
      lon: Number(originLon.toFixed(6)),
      lat: Number((originLat + 6 * stepLat).toFixed(6)),
    },
    {
      id: "grid_se",
      name: "SE Perimeter Node (Av-7 / St-1)",
      category: "junction",
      lon: Number((originLon + 6 * stepLon).toFixed(6)),
      lat: Number(originLat.toFixed(6)),
    },
  ];

  const graph = buildRoadGraph(roads);

  return {
    studyAreaId: "pilot_synthetic_grid",
    roads,
    waterways: [],
    landmarks,
    buildings: [],
    nodeCount: graph.routableCore.size,
    directedEdgeCount: graph.edges.length,
  };
}
