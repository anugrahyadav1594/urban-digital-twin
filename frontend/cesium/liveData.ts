/**
 * Live PostGIS geometry -> Cesium entities.
 *
 * The viewer originally drew a procedural city (boxes from lib/city-model).
 * These loaders replace that with the real ingested OSM data served by
 * GET /api/v1/layers/{id}/geojson, so what is on the globe is what is in the
 * database: true building footprints extruded to their tagged height, the
 * actual road centrelines, real named facilities.
 *
 * Every loader is defensive: if the request fails it returns 0 and the caller
 * keeps the synthetic fallback, with the DEMO DATA banner already visible.
 */
import { api } from "@/lib/api/client";

/**
 * Draw caps.
 *
 * Cesium's Entity API allocates one primitive per feature, so the full
 * 7,110 extruded footprints + 8,811 polylines will stall a software renderer
 * and lag weaker GPUs. These caps keep the globe interactive; raise them with
 * NEXT_PUBLIC_MAX_BUILDINGS / NEXT_PUBLIC_MAX_ROADS on a capable machine.
 * The layer panel always reports the true database totals from GET /layers.
 */
const envInt = (v: string | undefined, dflt: number) => {
  const n = v ? parseInt(v, 10) : NaN;
  return Number.isFinite(n) && n > 0 ? n : dflt;
};
const MAX_BUILDINGS = envInt(process.env.NEXT_PUBLIC_MAX_BUILDINGS, 3000);
const MAX_ROADS = envInt(process.env.NEXT_PUBLIC_MAX_ROADS, 4000);

type Cesium = any;

const COLORS = {
  buildingLow: "#63788f",
  buildingMid: "#7d93b3",
  buildingHigh: "#9fb6d6",
  road: "#94a3b8",
  roadMajor: "#f8fafc",
  water: "#38bdf8",
  facility: "#34d399"
};

/** Ring array -> flat lon,lat list Cesium wants. */
function flatten(ring: number[][]): number[] {
  const out: number[] = [];
  for (const c of ring) { out.push(c[0], c[1]); }
  return out;
}

/** Yield every polygon (outer ring only) from Polygon | MultiPolygon. */
function* polygons(geom: any): Generator<number[][]> {
  if (!geom) return;
  if (geom.type === "Polygon") yield geom.coordinates[0];
  else if (geom.type === "MultiPolygon") for (const p of geom.coordinates) yield p[0];
}

/** Yield every line from LineString | MultiLineString. */
function* lines(geom: any): Generator<number[][]> {
  if (!geom) return;
  if (geom.type === "LineString") yield geom.coordinates;
  else if (geom.type === "MultiLineString") for (const l of geom.coordinates) yield l;
}

function num(v: unknown, dflt: number): number {
  const n = typeof v === "string" ? parseFloat(v) : (v as number);
  return Number.isFinite(n) ? (n as number) : dflt;
}

/**
 * Real building footprints, extruded.
 * Uses height_m when OSM had it, else floors * 3.2, else a 6 m default.
 */
export async function loadBuildings(C: Cesium, ds: any, limit = MAX_BUILDINGS): Promise<number> {
  const gj = await api.getLayerGeoJSON(`buildings?limit=${limit}`);
  if (!gj?.features?.length) return 0;
  ds.entities.removeAll();
  let n = 0;
  for (const f of gj.features) {
    const p = f.properties ?? {};
    const floors = num(p.floors, 0);
    const h = num(p.height_m, 0) || (floors > 0 ? floors * 3.2 : 6);
    // Thresholds match the real height distribution of this city (median
    // ~10 m). The old >32/>16 bands put 98% of buildings in one colour.
    const col = h > 13 ? COLORS.buildingHigh : h > 6 ? COLORS.buildingMid : COLORS.buildingLow;
    for (const ring of polygons(f.geometry)) {
      if (ring.length < 4) continue;
      ds.entities.add({
        id: `building:${p.id}:${n}`,
        polygon: {
          hierarchy: C.Cartesian3.fromDegreesArray(flatten(ring)),
          material: C.Color.fromCssColorString(col).withAlpha(0.95),
          extrudedHeight: h,
          height: 0,
          outline: true,
          outlineColor: C.Color.fromCssColorString("#0b1220").withAlpha(0.6)
        },
        properties: { kind: "building", ref: String(p.id), height: h, floors }
      });
      n++;
    }
  }
  return n;
}

/** Real road centrelines, width by class. */
export async function loadRoads(C: Cesium, ds: any, limit = MAX_ROADS): Promise<number> {
  const gj = await api.getLayerGeoJSON(`roads?limit=${limit}`);
  if (!gj?.features?.length) return 0;
  ds.entities.removeAll();
  const MAJOR = new Set(["motorway", "trunk", "primary", "arterial"]);
  let n = 0;
  for (const f of gj.features) {
    const p = f.properties ?? {};
    const major = MAJOR.has(String(p.road_class ?? "").toLowerCase());
    for (const line of lines(f.geometry)) {
      if (line.length < 2) continue;
      ds.entities.add({
        id: `road:${p.id}:${n}`,
        polyline: {
          positions: C.Cartesian3.fromDegreesArray(flatten(line)),
          width: major ? 5 : 2.5,
          material: C.Color.fromCssColorString(major ? COLORS.roadMajor : COLORS.road).withAlpha(0.8),
          clampToGround: true
        },
        properties: { kind: "road", ref: String(p.id), roadClass: p.road_class }
      });
      n++;
    }
  }
  return n;
}

/** Real facilities: hospitals, clinics, schools, fire stations. */
export async function loadFacilities(C: Cesium, ds: any): Promise<number> {
  const gj = await api.getLayerGeoJSON("facilities?limit=2000");
  if (!gj?.features?.length) return 0;
  ds.entities.removeAll();
  let n = 0;
  for (const f of gj.features) {
    const p = f.properties ?? {};
    const g = f.geometry;
    if (!g) continue;
    // facilities is a mixed GEOMETRY column; reduce anything areal to a point
    let lon: number, lat: number;
    if (g.type === "Point") { [lon, lat] = g.coordinates; }
    else {
      const ring = polygons(g).next().value as number[][] | undefined;
      if (!ring?.length) continue;
      lon = ring.reduce((a, c) => a + c[0], 0) / ring.length;
      lat = ring.reduce((a, c) => a + c[1], 0) / ring.length;
    }
    const type = String(p.type ?? "facility");
    const glyph = type[0]?.toUpperCase() ?? "F";
    ds.entities.add({
      id: `facility:${p.id}`,
      position: C.Cartesian3.fromDegrees(lon, lat, 40),
      point: {
        pixelSize: 11,
        color: C.Color.fromCssColorString(COLORS.facility),
        outlineColor: C.Color.fromCssColorString("#04140d"),
        outlineWidth: 2
      },
      label: {
        text: `${glyph} · ${p.name ?? type}`,
        font: "11px monospace",
        fillColor: C.Color.fromCssColorString("#d1fae5"),
        showBackground: true,
        backgroundColor: C.Color.fromCssColorString("#04211a").withAlpha(0.75),
        pixelOffset: new C.Cartesian2(0, -18),
        verticalOrigin: C.VerticalOrigin.BOTTOM,
        distanceDisplayCondition: new C.DistanceDisplayCondition(0, 14000)
      },
      properties: { kind: "facility", ref: String(p.id), type }
    });
    n++;
  }
  return n;
}

/** Real water bodies from OSM. */
export async function loadWater(C: Cesium, ds: any): Promise<number> {
  const gj = await api.getLayerGeoJSON("water?limit=2000");
  if (!gj?.features?.length) return 0;
  let n = 0;
  for (const f of gj.features) {
    const p = f.properties ?? {};
    for (const ring of polygons(f.geometry)) {
      if (ring.length < 4) continue;
      ds.entities.add({
        id: `water:${p.id}:${n}`,
        polygon: {
          hierarchy: C.Cartesian3.fromDegreesArray(flatten(ring)),
          material: C.Color.fromCssColorString(COLORS.water).withAlpha(0.55),
          height: 2
        },
        properties: { kind: "water", ref: String(p.id) }
      });
      n++;
    }
  }
  return n;
}

/** Real land parcels, tinted by flood risk. */
export async function loadParcels(C: Cesium, dsParcels: any, dsFlood: any): Promise<number> {
  const gj = await api.getLayerGeoJSON("parcels?limit=5000");
  if (!gj?.features?.length) return 0;
  let n = 0;
  for (const f of gj.features) {
    const p = f.properties ?? {};
    const risk = num(p.flood_risk, 0);
    for (const ring of polygons(f.geometry)) {
      if (ring.length < 4) continue;
      const pos = C.Cartesian3.fromDegreesArray(flatten(ring));
      dsParcels.entities.add({
        id: `parcel:${p.id}:${n}`,
        polygon: {
          hierarchy: pos,
          material: C.Color.fromCssColorString("#22d3ee").withAlpha(0.18),
          outline: true,
          outlineColor: C.Color.fromCssColorString("#22d3ee").withAlpha(0.7),
          height: 3
        },
        properties: { kind: "parcel", ref: String(p.id), zoning: p.zoning, floodRisk: risk }
      });
      if (risk >= 0.3) {
        dsFlood.entities.add({
          id: `flood:${p.id}:${n}`,
          polygon: {
            hierarchy: pos,
            material: C.Color.fromCssColorString(risk >= 0.6 ? "#ef4444" : "#f59e0b").withAlpha(0.4),
            height: 4
          },
          properties: { kind: "parcel", ref: String(p.id) }
        });
      }
      n++;
    }
  }
  return n;
}

/** Load every live layer; returns per-layer counts actually drawn. */
export async function loadAllLive(
  C: Cesium,
  ds: Record<string, any>
): Promise<Record<string, number>> {
  const [buildings, roads, facilities, water, parcels] = await Promise.all([
    loadBuildings(C, ds.buildings).catch(() => 0),
    loadRoads(C, ds.roads).catch(() => 0),
    loadFacilities(C, ds.facilities).catch(() => 0),
    loadWater(C, ds.water).catch(() => 0),
    loadParcels(C, ds.parcels, ds.flood).catch(() => 0)
  ]);
  return { buildings, roads, facilities, water, parcels };
}
