/**
 * Deterministic procedural pilot-city model.
 *
 * In production these records come from the backend
 * (GET /city, /layers/{id}/features, /features/{id}).
 * Here a seeded generator produces a stable synthetic city so the whole
 * workspace - Cesium, Inspector, Analysis, Comparison - shares one
 * source of truth and every id resolves to a real map entity.
 */
import { CITY_CENTER } from "./constants";
import type { CityInfo, FeatureRecord } from "@/types";

function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const rnd = mulberry32(20260816);

export const ZONING = ["R1", "R2", "R3", "C1", "C2", "I1", "PS", "G1"] as const;
export const ZONE_LABEL: Record<string, string> = {
  R1: "Residential low", R2: "Residential medium", R3: "Residential high",
  C1: "Commercial", C2: "Mixed use", I1: "Industrial", PS: "Public / semi-public", G1: "Green / open"
};
export const ZONE_COLOR: Record<string, string> = {
  R1: "#7dd3fc", R2: "#38bdf8", R3: "#0ea5e9", C1: "#fbbf24", C2: "#f59e0b",
  I1: "#a78bfa", PS: "#f472b6", G1: "#4ade80"
};
export const RISK = ["Low", "Medium", "High"] as const;

export type Parcel = {
  id: string; idx: number; lon: number; lat: number;
  areaM2: number; zoning: string; flood: (typeof RISK)[number];
  population: number; heightM: number; floors: number; ward: string;
  landValue: number; slopePct: number; roadAccessM: number;
};

export type RoadSeg = { id: string; name: string; type: "Arterial" | "Sub-arterial" | "Local"; path: [number, number][]; lanes: number; speed: number };
export type Facility = { id: string; name: string; type: "Hospital" | "School" | "Fire Station" | "Metro"; lon: number; lat: number; capacity: number };

const GRID = 26;            // 26 x 26 blocks
const STEP = 0.0022;        // ~240 m
const O_LON = CITY_CENTER.lon - (GRID * STEP) / 2;
const O_LAT = CITY_CENTER.lat - (GRID * STEP) / 2;

function buildParcels(): Parcel[] {
  const out: Parcel[] = [];
  let n = 0;
  for (let r = 0; r < GRID; r++) {
    for (let c = 0; c < GRID; c++) {
      const jitterLon = (rnd() - 0.5) * STEP * 0.25;
      const jitterLat = (rnd() - 0.5) * STEP * 0.25;
      const lon = O_LON + c * STEP + jitterLon;
      const lat = O_LAT + r * STEP + jitterLat;
      const dx = c - GRID / 2, dy = r - GRID / 2;
      const dist = Math.sqrt(dx * dx + dy * dy) / (GRID / 2);          // 0 centre -> 1 edge
      const density = Math.max(0.06, 1 - dist);                        // CBD falloff
      const zRoll = rnd();
      const zoning =
        density > 0.72 ? (zRoll > 0.55 ? "C1" : "R3") :
        density > 0.5 ? (zRoll > 0.7 ? "C2" : "R3") :
        density > 0.32 ? (zRoll > 0.75 ? "I1" : "R2") :
        zRoll > 0.86 ? "PS" : zRoll > 0.7 ? "G1" : "R1";
      const river = Math.abs((r - GRID * 0.68) + Math.sin(c / 3.1) * 2.2);
      const flood = river < 1.15 ? "High" : river < 2.6 ? "Medium" : "Low";
      const floors = zoning === "G1" ? 0 : Math.max(1, Math.round(density * 16 * (0.55 + rnd() * 0.9)));
      out.push({
        id: "parcel_" + (1000 + n),
        idx: n,
        lon, lat,
        areaM2: Math.round(2200 + rnd() * 7800),
        zoning,
        flood: flood as Parcel["flood"],
        population: zoning === "G1" ? 0 : Math.round(density * 900 * (0.4 + rnd())),
        heightM: floors * 3.2,
        floors,
        ward: "W-" + (1 + Math.floor(r / 5)) + String.fromCharCode(65 + Math.floor(c / 7)),
        landValue: Math.round((18 + density * 70) * (0.7 + rnd() * 0.6)),
        slopePct: Math.round(rnd() * 9 * 10) / 10,
        roadAccessM: Math.round(20 + rnd() * 260)
      });
      n++;
    }
  }
  return out;
}

export const PARCELS: Parcel[] = buildParcels();
export const PARCEL_BY_ID = new Map(PARCELS.map((p) => [p.id, p]));

export const ROADS: RoadSeg[] = (() => {
  const roads: RoadSeg[] = [];
  for (let r = 0; r < GRID; r += 4) {
    roads.push({
      id: "road_h" + r,
      name: "Corridor H-" + (r / 4 + 1),
      type: r % 8 === 0 ? "Arterial" : "Sub-arterial",
      lanes: r % 8 === 0 ? 6 : 4,
      speed: r % 8 === 0 ? 60 : 45,
      path: Array.from({ length: GRID }, (_, c) => [O_LON + c * STEP, O_LAT + r * STEP] as [number, number])
    });
  }
  for (let c = 0; c < GRID; c += 4) {
    roads.push({
      id: "road_v" + c,
      name: "Corridor V-" + (c / 4 + 1),
      type: c % 8 === 0 ? "Arterial" : "Sub-arterial",
      lanes: c % 8 === 0 ? 6 : 4,
      speed: c % 8 === 0 ? 60 : 45,
      path: Array.from({ length: GRID }, (_, r) => [O_LON + c * STEP, O_LAT + r * STEP] as [number, number])
    });
  }
  return roads;
})();

export const FACILITIES: Facility[] = [
  { id: "fac_h1", name: "Civil Hospital", type: "Hospital", lon: O_LON + 6 * STEP, lat: O_LAT + 7 * STEP, capacity: 320 },
  { id: "fac_h2", name: "Sector 9 Hospital", type: "Hospital", lon: O_LON + 18 * STEP, lat: O_LAT + 6 * STEP, capacity: 180 },
  { id: "fac_s1", name: "Model School", type: "School", lon: O_LON + 9 * STEP, lat: O_LAT + 16 * STEP, capacity: 1400 },
  { id: "fac_s2", name: "East Public School", type: "School", lon: O_LON + 20 * STEP, lat: O_LAT + 18 * STEP, capacity: 900 },
  { id: "fac_f1", name: "Fire Station North", type: "Fire Station", lon: O_LON + 13 * STEP, lat: O_LAT + 21 * STEP, capacity: 6 },
  { id: "fac_m1", name: "Metro Interchange", type: "Metro", lon: O_LON + 13 * STEP, lat: O_LAT + 12 * STEP, capacity: 0 }
];

export const FLOOD_ZONE: [number, number][] = Array.from({ length: GRID }, (_, c) => [O_LON + c * STEP, O_LAT + (GRID * 0.68 - Math.sin(c / 3.1) * 2.2) * STEP] as [number, number]);

export const CITY: CityInfo = {
  id: "city_pilot_01",
  name: "Nagar-X Pilot Sector",
  state: "Maharashtra",
  datasetVersion: "ds_2026.02",
  crs: "EPSG:32643 / WGS84",
  areaKm2: Math.round(GRID * STEP * 111 * GRID * STEP * 111 * 10) / 10,
  population: PARCELS.reduce((s, p) => s + p.population, 0),
  households: Math.round(PARCELS.reduce((s, p) => s + p.population, 0) / 4.3),
  wards: 30,
  updatedAt: "2026-07-28",
  center: CITY_CENTER
};

export function featureFromId(id: string): FeatureRecord | null {
  const p = PARCEL_BY_ID.get(id);
  if (p) {
    return {
      id: p.id,
      kind: p.floors > 0 ? "parcel" : "zone",
      name: "Parcel #" + p.id.split("_")[1],
      position: { lon: p.lon, lat: p.lat },
      attributes: {
        Area: p.areaM2 + " m²",
        Zoning: p.zoning + " — " + ZONE_LABEL[p.zoning],
        Ward: p.ward,
        Floors: p.floors,
        "Built height": p.heightM.toFixed(1) + " m",
        Population: p.population,
        "Flood risk": p.flood,
        "Land value": "₹" + p.landValue + "k / m²",
        Slope: p.slopePct + " %",
        "Road access": p.roadAccessM + " m",
        "Dataset version": CITY.datasetVersion
      }
    };
  }
  const f = FACILITIES.find((x) => x.id === id);
  if (f) {
    return {
      id: f.id, kind: "facility", name: f.name,
      position: { lon: f.lon, lat: f.lat },
      attributes: { Type: f.type, Capacity: f.capacity, Status: "Operational", "Dataset version": CITY.datasetVersion }
    };
  }
  const r = ROADS.find((x) => x.id === id);
  if (r) {
    return {
      id: r.id, kind: "road", name: r.name,
      position: { lon: r.path[Math.floor(r.path.length / 2)][0], lat: r.path[Math.floor(r.path.length / 2)][1] },
      attributes: { Class: r.type, Lanes: r.lanes, "Design speed": r.speed + " km/h", Length: (r.path.length * 0.24).toFixed(1) + " km" }
    };
  }
  return null;
}
