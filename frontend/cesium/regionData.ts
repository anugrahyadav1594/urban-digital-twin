/**
 * Comparison-region geometry -> Cesium entities.
 *
 * The pilot sector (Adivali-devad) is drawn by liveData.ts from the canonical
 * layer tables. The batch extractor also produced three comparison areas
 * (JNPT Port, Chandigarh Sector 17, Rotterdam) in per-region tables which had
 * no route on the API, so they were never reachable from the UI.
 *
 * GET /api/v1/regions/{id}/geojson returns all of a region's layers in one
 * FeatureCollection with `layer` tagged per feature, so this is a single
 * request and one pass of styling.
 *
 * These are display-only: the analysis engines still run against the pilot
 * sector's canonical tables, not against these.
 */
import { api } from "@/lib/api/client";

type Cesium = any;

export type RegionInfo = {
  id: string;
  label: string;
  note?: string;
  bounds: [number, number, number, number];
  center: { lon: number; lat: number };
  layers: Record<string, number>;
  featureCount: number;
  available: boolean;
};

/** Per-layer styling. Kept flat and obvious so the legend can mirror it. */
const STYLE: Record<string, { color: string; width: number; alpha: number }> = {
  roads: { color: "#94a3b8", width: 2, alpha: 0.9 },
  bridges: { color: "#f59e0b", width: 4, alpha: 1.0 },
  water: { color: "#0ea5e9", width: 1, alpha: 0.45 },
  buildings: { color: "#cbd5e1", width: 1, alpha: 0.75 },
};

/** Flat [lon,lat,lon,lat,...] from a GeoJSON ring, dropping any z. */
function flatten(ring: number[][]): number[] {
  const out: number[] = [];
  for (const p of ring) {
    if (Number.isFinite(p?.[0]) && Number.isFinite(p?.[1])) out.push(p[0], p[1]);
  }
  return out;
}

/** Extruded footprint for a polygon ring set. */
function addPolygon(
  C: Cesium,
  ds: any,
  rings: number[][][],
  layer: string,
  region: string,
  id: string
) {
  const outer = flatten(rings[0] || []);
  if (outer.length < 6) return 0; // fewer than 3 vertices is not a polygon
  const holes = rings
    .slice(1)
    .map((r) => flatten(r))
    .filter((f) => f.length >= 6)
    .map((f) => new C.PolygonHierarchy(C.Cartesian3.fromDegreesArray(f)));

  const st = STYLE[layer] ?? STYLE.buildings;
  const isBuilding = layer === "buildings";

  ds.entities.add({
    id,
    properties: { layer, region },
    polygon: {
      hierarchy: new C.PolygonHierarchy(
        C.Cartesian3.fromDegreesArray(outer),
        holes
      ),
      material: C.Color.fromCssColorString(st.color).withAlpha(st.alpha),
      // Buildings get a nominal extrusion: the comparison tables carry no
      // reliable height tag, so a flat block reads as built form without
      // implying a surveyed height.
      extrudedHeight: isBuilding ? 12 : undefined,
      height: isBuilding ? 0 : undefined,
      perPositionHeight: false,
      outline: isBuilding,
      outlineColor: C.Color.fromCssColorString("#0f172a").withAlpha(0.35),
      classificationType: isBuilding ? undefined : C.ClassificationType.TERRAIN,
    },
  });
  return 1;
}

/** Draped polyline for a line string. */
function addLine(
  C: Cesium,
  ds: any,
  coords: number[][],
  layer: string,
  region: string,
  id: string
) {
  const flat = flatten(coords);
  if (flat.length < 4) return 0; // need two points
  const st = STYLE[layer] ?? STYLE.roads;
  ds.entities.add({
    id,
    properties: { layer, region },
    polyline: {
      positions: C.Cartesian3.fromDegreesArray(flat),
      width: st.width,
      material: C.Color.fromCssColorString(st.color).withAlpha(st.alpha),
      clampToGround: true,
    },
  });
  return 1;
}

/** List available regions; [] if the backend is unreachable. */
export async function listRegions(): Promise<RegionInfo[]> {
  try {
    return ((await api.listRegions()) as RegionInfo[]) ?? [];
  } catch {
    return [];
  }
}

/**
 * Draw one region into `ds`, replacing whatever it held.
 * Returns per-layer counts drawn plus the server's per-layer status.
 */
export async function loadRegion(
  C: Cesium,
  ds: any,
  regionId: string
): Promise<{
  counts: Record<string, number>;
  status: Record<string, string>;
  total: number;
  center?: { lon: number; lat: number };
  bounds?: [number, number, number, number];
}> {
  ds.entities.removeAll();

  let fc: any = null;
  try {
    fc = await api.getRegionGeoJSON(regionId);
  } catch {
    fc = null;
  }
  if (!fc || !Array.isArray(fc.features)) {
    return { counts: {}, status: { error: "unreachable" }, total: 0 };
  }

  const counts: Record<string, number> = {};
  let i = 0;

  // Entities are batched by suspending change events; without this Cesium
  // re-evaluates the collection on every single add.
  ds.entities.suspendEvents();
  try {
    for (const f of fc.features) {
      const g = f?.geometry;
      if (!g) continue;
      const layer = String(f.properties?.layer ?? "roads");
      const id = `region-${regionId}-${i++}`;
      let n = 0;

      switch (g.type) {
        case "Polygon":
          n = addPolygon(C, ds, g.coordinates, layer, regionId, id);
          break;
        case "MultiPolygon":
          // Each part is its own entity; ids must stay unique.
          g.coordinates.forEach((poly: number[][][], k: number) => {
            n += addPolygon(C, ds, poly, layer, regionId, `${id}-${k}`);
          });
          break;
        case "LineString":
          n = addLine(C, ds, g.coordinates, layer, regionId, id);
          break;
        case "MultiLineString":
          g.coordinates.forEach((line: number[][], k: number) => {
            n += addLine(C, ds, line, layer, regionId, `${id}-${k}`);
          });
          break;
        default:
          break; // points carry no useful footprint at this zoom
      }
      if (n) counts[layer] = (counts[layer] ?? 0) + n;
    }
  } finally {
    ds.entities.resumeEvents();
  }

  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  return {
    counts,
    status: fc.layerStatus ?? {},
    total,
    center: fc.center,
    bounds: fc.bounds,
  };
}

/**
 * Fly to a region's bounds.
 *
 * A new overlay that appears outside the current view reads as "nothing
 * happened", so switching region must always move the camera.
 */
export function flyToRegion(
  C: Cesium,
  viewer: any,
  bounds: [number, number, number, number],
  duration = 1.8
) {
  if (!viewer || !bounds || bounds.length !== 4) return;
  const [w, s, e, n] = bounds;
  viewer.camera.flyTo({
    destination: C.Rectangle.fromDegrees(w, s, e, n),
    duration,
  });
}

/** Toggle one layer's visibility within an already-loaded region. */
export function setRegionLayerVisible(ds: any, layer: string, visible: boolean) {
  if (!ds) return;
  ds.entities.suspendEvents();
  try {
    for (const ent of ds.entities.values) {
      const l = ent.properties?.layer?.getValue?.() ?? ent.properties?.layer;
      if (l === layer) ent.show = visible;
    }
  } finally {
    ds.entities.resumeEvents();
  }
}