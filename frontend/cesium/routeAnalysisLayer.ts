/**
 * Cesium synchronization helpers for NagarX disaster-aware route analysis,
 * study-area OpenStreetMap / benchmark networks, and regional GeoJSON overlays.
 */
import type {
  AffectedNetworkPreview,
  DisasterScenarioConfig,
  LoadedStudyAreaDataset,
  MapInteractionMode,
  RouteComparisonResult,
  RouteWaypoint,
} from "@/types";
import { circleToPolygon } from "@/lib/routing-engine";

export async function loadRegionalReferenceOverlays(
  Cesium: any,
  ds: Record<string, any>
): Promise<void> {
  const C = (hex: string, a = 1) =>
    Cesium.Color.fromCssColorString(hex).withAlpha(a);

  // 1. Regional National Highways (public/data/india-highways.json)
  try {
    const hwRes = await fetch("/data/india-highways.json");
    if (hwRes.ok) {
      const geo = await hwRes.json();
      const features = Array.isArray(geo?.features) ? geo.features : [];
      features.forEach((f: any, idx: number) => {
        const coords = f?.geometry?.coordinates;
        if (f?.geometry?.type !== "LineString" || !Array.isArray(coords)) return;
        const flat: number[] = [];
        for (const c of coords) {
          if (Number.isFinite(c?.[0]) && Number.isFinite(c?.[1])) {
            flat.push(c[0], c[1]);
          }
        }
        if (flat.length < 4) return;
        const ref = f?.properties?.ref || "NH";
        const name = f?.properties?.name || ref;
        const mid = coords[Math.floor(coords.length / 2)];
        ds.highways?.entities.add({
          id: `reg_nh_${idx}`,
          polyline: {
            positions: Cesium.Cartesian3.fromDegreesArray(flat),
            width: 3.5,
            material: C("#facc15", 0.65),
            clampToGround: true,
          },
          position: mid
            ? Cesium.Cartesian3.fromDegrees(mid[0], mid[1], 30)
            : undefined,
          label: mid
            ? {
                text: `${ref}`,
                font: "600 10px monospace",
                fillColor: C("#fef08a"),
                showBackground: true,
                backgroundColor: C("#1e293b", 0.82),
                distanceDisplayCondition:
                  new Cesium.DistanceDisplayCondition(8000, 350000),
              }
            : undefined,
          properties: { kind: "highway", name },
        });
      });
    }
  } catch {
    // Non-fatal optional overlay
  }

  // 2. Pune River & Reservoir Reference Hydrography (public/data/pune-waterbodies.json)
  try {
    const wtRes = await fetch("/data/pune-waterbodies.json");
    if (wtRes.ok) {
      const geo = await wtRes.json();
      const features = Array.isArray(geo?.features) ? geo.features : [];
      features.forEach((f: any, idx: number) => {
        const geom = f?.geometry;
        const name = f?.properties?.name || "Regional Waterbody";
        if (geom?.type === "LineString" && Array.isArray(geom.coordinates)) {
          const flat = geom.coordinates.flat();
          if (flat.length >= 4) {
            ds.water?.entities.add({
              id: `pune_wt_${idx}`,
              polyline: {
                positions: Cesium.Cartesian3.fromDegreesArray(flat),
                width: 5,
                material: C("#0ea5e9", 0.78),
                clampToGround: true,
              },
              properties: { kind: "water", name },
            });
          }
        } else if (
          geom?.type === "Polygon" &&
          Array.isArray(geom.coordinates?.[0])
        ) {
          const flat = geom.coordinates[0].flat();
          if (flat.length >= 6) {
            ds.water?.entities.add({
              id: `pune_wt_${idx}`,
              polygon: {
                hierarchy: Cesium.Cartesian3.fromDegreesArray(flat),
                material: C("#0284c7", 0.55),
              },
              properties: { kind: "water", name },
            });
          }
        }
      });
    }
  } catch {
    // Non-fatal optional overlay
  }
}

export function renderStudyAreaNetworkOnGlobe(
  Cesium: any,
  ds: Record<string, any>,
  dataset: LoadedStudyAreaDataset
): void {
  const C = (hex: string, a = 1) =>
    Cesium.Color.fromCssColorString(hex).withAlpha(a);

  // Clear study-area-specific entities without deleting regional reference overlays
  const clearPrefixed = (source: any, keepPrefix: string | null) => {
    if (!source) return;
    const toRemove: any[] = [];
    for (const ent of source.entities.values) {
      if (keepPrefix && String(ent.id).startsWith(keepPrefix)) continue;
      toRemove.push(ent);
    }
    for (const ent of toRemove) {
      source.entities.remove(ent);
    }
  };

  clearPrefixed(ds.roads, null);
  clearPrefixed(ds.water, "pune_wt_");
  clearPrefixed(ds.buildings, null);
  clearPrefixed(ds.facilities, null);

  // 1. Waterways (e.g., Kalundre River & local streams)
  for (const w of dataset.waterways) {
    const flat = w.coordinates.flat();
    if (flat.length < 4) continue;
    if (w.kind === "polygon" && flat.length >= 6) {
      ds.water?.entities.add({
        id: w.id,
        polygon: {
          hierarchy: Cesium.Cartesian3.fromDegreesArray(flat),
          material: C("#0284c7", 0.5),
          outline: true,
          outlineColor: C("#38bdf8", 0.65),
        },
        properties: { kind: "water", name: w.name },
      });
    } else {
      const mid = w.coordinates[Math.floor(w.coordinates.length / 2)];
      ds.water?.entities.add({
        id: w.id,
        position: mid
          ? Cesium.Cartesian3.fromDegrees(mid[0], mid[1], 10)
          : undefined,
        polyline: {
          positions: Cesium.Cartesian3.fromDegreesArray(flat),
          width: 7,
          material: C("#0ea5e9", 0.78),
          clampToGround: true,
        },
        label:
          mid && w.name.includes("Kalundre")
            ? {
                text: w.name,
                font: "600 11px sans-serif",
                fillColor: C("#bae6fd"),
                showBackground: true,
                backgroundColor: C("#082f49", 0.8),
                pixelOffset: new Cesium.Cartesian2(0, -10),
                distanceDisplayCondition:
                  new Cesium.DistanceDisplayCondition(0, 12000),
              }
            : undefined,
        properties: { kind: "water", name: w.name },
      });
    }
  }

  // 2. Road segments styled by road hierarchy
  for (const r of dataset.roads) {
    const flat = r.coordinates.flat();
    if (flat.length < 4) continue;
    const isMajor =
      r.roadClass === "motorway" ||
      r.roadClass === "primary" ||
      r.roadClass === "arterial";
    const isSecondary =
      r.roadClass === "secondary" ||
      r.roadClass === "tertiary" ||
      r.roadClass === "sub-arterial";
    const color = r.bridge
      ? "#cbd5e1"
      : isMajor
      ? "#e2e8f0"
      : isSecondary
      ? "#94a3b8"
      : "#64748b";
    const width = isMajor ? 5 : isSecondary ? 3.5 : 2.2;

    ds.roads?.entities.add({
      id: r.id,
      polyline: {
        positions: Cesium.Cartesian3.fromDegreesArray(flat),
        width,
        material: C(color, isMajor ? 0.88 : 0.68),
        clampToGround: true,
      },
      properties: {
        kind: "road",
        roadId: r.id,
        name: r.name,
        roadClass: r.roadClass,
      },
    });
  }

  // 3. Authentic OSM building footprints (extruded 3D polygons)
  for (const b of dataset.buildings) {
    const flat = b.coordinates.flat();
    if (flat.length < 6) continue;
    ds.buildings?.entities.add({
      id: b.id,
      polygon: {
        hierarchy: Cesium.Cartesian3.fromDegreesArray(flat),
        extrudedHeight: b.heightM,
        height: 0,
        material: C(
          b.floors >= 6 ? "#94a3b8" : b.floors >= 4 ? "#64748b" : "#475569",
          0.88
        ),
        outline: true,
        outlineColor: C("#0f172a", 0.7),
      },
      properties: { kind: "building", name: b.name || b.id },
    });
  }

  // 4. Landmarks & emergency/medical facilities
  for (const lm of dataset.landmarks.slice(0, 24)) {
    const isMedical = lm.category === "hospital" || lm.category === "clinic";
    const isFire = lm.category === "fire_station";
    const col = isFire ? "#fb923c" : isMedical ? "#34d399" : "#38bdf8";
    const tag = isFire ? "FIRE" : isMedical ? "MED" : "NODE";

    ds.facilities?.entities.add({
      id: lm.id,
      position: Cesium.Cartesian3.fromDegrees(lm.lon, lm.lat, 18),
      point: {
        pixelSize: 8,
        color: C(col, 0.95),
        outlineColor: C("#020617", 1),
        outlineWidth: 2,
      },
      label: {
        text: `${tag} · ${lm.name}`,
        font: "500 10.5px sans-serif",
        fillColor: C("#f1f5f9"),
        showBackground: true,
        backgroundColor: C("#0f172a", 0.82),
        pixelOffset: new Cesium.Cartesian2(0, -16),
        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 7500),
      },
      properties: { kind: "facility", name: lm.name },
    });
  }
}

export function syncRouteAnalysisOverlay(
  Cesium: any,
  routeDs: any,
  params: {
    origin: RouteWaypoint | null;
    destination: RouteWaypoint | null;
    scenario: DisasterScenarioConfig;
    affectedPreview: AffectedNetworkPreview | null;
    result: RouteComparisonResult | null;
    interactionMode: MapInteractionMode;
    drawingVertices: [number, number][];
  }
): void {
  if (!routeDs) return;
  const C = (hex: string, a = 1) =>
    Cesium.Color.fromCssColorString(hex).withAlpha(a);

  routeDs.entities.removeAll();

  const {
    origin,
    destination,
    scenario,
    affectedPreview,
    result,
    interactionMode,
    drawingVertices,
  } = params;

  // 1. Active Simulated Hazard Zone (Polygon or Circle)
  if (scenario.active) {
    let ring: [number, number][] = [];
    if (scenario.geometryKind === "polygon" && scenario.polygon.length >= 3) {
      ring = scenario.polygon;
    } else if (
      scenario.geometryKind === "circle" &&
      scenario.center &&
      scenario.radiusM > 0
    ) {
      ring = circleToPolygon(scenario.center, scenario.radiusM, 36);
    }

    if (ring.length >= 3) {
      const closedRing = [...ring, ring[0]];
      const flat = ring.flat();
      const closedFlat = closedRing.flat();
      const cx = ring.reduce((s, p) => s + p[0], 0) / ring.length;
      const cy = ring.reduce((s, p) => s + p[1], 0) / ring.length;

      const fillHex =
        scenario.severityMode === "closed" ? "#ef4444" : "#f59e0b";

      routeDs.entities.add({
        id: "nx_hazard_zone",
        polygon: {
          hierarchy: Cesium.Cartesian3.fromDegreesArray(flat),
          material: C(fillHex, 0.22),
          classificationType: Cesium.ClassificationType.BOTH,
        },
        polyline: {
          positions: Cesium.Cartesian3.fromDegreesArray(closedFlat),
          width: 3,
          material: new Cesium.PolylineDashMaterialProperty({
            color: C(fillHex, 0.95),
            dashLength: 14,
          }),
          clampToGround: true,
        },
      });

      routeDs.entities.add({
        id: "nx_hazard_label",
        position: Cesium.Cartesian3.fromDegrees(cx, cy, 35),
        label: {
          text: `SIMULATED ${scenario.type.replace("_", " ").toUpperCase()}\n${scenario.name}`,
          font: "600 11px sans-serif",
          fillColor: C("#fecaca"),
          showBackground: true,
          backgroundColor: C("#450a0a", 0.88),
          pixelOffset: new Cesium.Cartesian2(0, -8),
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
          distanceDisplayCondition: new Cesium.DistanceDisplayCondition(
            0,
            22000
          ),
        },
      });
    }
  }

  // 2. Interactive Polygon Drawing Preview
  if (interactionMode === "draw_hazard_polygon" && drawingVertices.length > 0) {
    drawingVertices.forEach((v, idx) => {
      routeDs.entities.add({
        id: `nx_draw_v_${idx}`,
        position: Cesium.Cartesian3.fromDegrees(v[0], v[1], 12),
        point: {
          pixelSize: 10,
          color: C("#f43f5e", 1),
          outlineColor: C("#ffffff", 1),
          outlineWidth: 2,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
        label: {
          text: `V${idx + 1}`,
          font: "700 10px monospace",
          fillColor: C("#ffffff"),
          showBackground: true,
          backgroundColor: C("#881337", 0.9),
          pixelOffset: new Cesium.Cartesian2(0, -16),
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
      });
    });

    if (drawingVertices.length >= 2) {
      const previewCoords =
        drawingVertices.length >= 3
          ? [...drawingVertices, drawingVertices[0]]
          : drawingVertices;
      routeDs.entities.add({
        id: "nx_draw_line",
        polyline: {
          positions: Cesium.Cartesian3.fromDegreesArray(previewCoords.flat()),
          width: 3,
          material: new Cesium.PolylineDashMaterialProperty({
            color: C("#fb7185", 0.95),
            dashLength: 12,
          }),
          clampToGround: true,
        },
      });
    }
    if (drawingVertices.length >= 3) {
      routeDs.entities.add({
        id: "nx_draw_poly",
        polygon: {
          hierarchy: Cesium.Cartesian3.fromDegreesArray(drawingVertices.flat()),
          material: C("#f43f5e", 0.18),
        },
      });
    }
  }

  // 3. Affected Road Segments (Closed & Penalized)
  const net = result?.affectedNetwork ?? affectedPreview;
  if (net && scenario.active) {
    net.closedSegments.slice(0, 260).forEach((seg, idx) => {
      const flat = seg.flat();
      if (flat.length < 4) return;
      routeDs.entities.add({
        id: `nx_closed_seg_${idx}`,
        polyline: {
          positions: Cesium.Cartesian3.fromDegreesArray(flat),
          width: 5,
          material: C("#ef4444", 0.92),
          clampToGround: true,
        },
      });
    });

    net.penalizedSegments.slice(0, 260).forEach((seg, idx) => {
      const flat = seg.flat();
      if (flat.length < 4) return;
      routeDs.entities.add({
        id: `nx_pen_seg_${idx}`,
        polyline: {
          positions: Cesium.Cartesian3.fromDegreesArray(flat),
          width: 4.5,
          material: new Cesium.PolylineDashMaterialProperty({
            color: C("#f59e0b", 0.95),
            dashLength: 10,
          }),
          clampToGround: true,
        },
      });
    });
  }

  // 4. Baseline Route (Dashed Royal Blue — distinct pattern & color)
  if (result?.baselineRoute.feasible && result.baselineRoute.path.length >= 2) {
    const baseFlat = result.baselineRoute.path.flat();
    routeDs.entities.add({
      id: "nx_baseline_route",
      polyline: {
        positions: Cesium.Cartesian3.fromDegreesArray(baseFlat),
        width: 6.5,
        material: new Cesium.PolylineDashMaterialProperty({
          color: C("#38bdf8", 0.96),
          gapColor: C("#1d4ed8", 0.55),
          dashLength: 18,
        }),
        clampToGround: true,
      },
    });

    const bMid =
      result.baselineRoute.path[
        Math.floor(result.baselineRoute.path.length * 0.38)
      ];
    if (bMid && result.baselineRoute.distanceM !== null) {
      routeDs.entities.add({
        id: "nx_baseline_label",
        position: Cesium.Cartesian3.fromDegrees(bMid[0], bMid[1], 26),
        label: {
          text: `BASELINE · ${(result.baselineRoute.distanceM / 1000).toFixed(2)} km`,
          font: "700 11px sans-serif",
          fillColor: C("#e0f2fe"),
          showBackground: true,
          backgroundColor: C("#0c4a6e", 0.9),
          pixelOffset: new Cesium.Cartesian2(0, -18),
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
      });
    }
  }

  // 5. Hazard-Aware Alternative Route (Solid Glowing High-Contrast Orange)
  if (
    result?.hazardAwareRoute.feasible &&
    result.hazardAwareRoute.path.length >= 2
  ) {
    const altFlat = result.hazardAwareRoute.path.flat();
    routeDs.entities.add({
      id: "nx_alt_route",
      polyline: {
        positions: Cesium.Cartesian3.fromDegreesArray(altFlat),
        width: 9,
        material: new Cesium.PolylineGlowMaterialProperty({
          color: C("#f97316", 0.98),
          glowPower: 0.22,
        }),
        clampToGround: true,
      },
    });

    const aMid =
      result.hazardAwareRoute.path[
        Math.floor(result.hazardAwareRoute.path.length * 0.62)
      ];
    if (aMid && result.hazardAwareRoute.distanceM !== null) {
      routeDs.entities.add({
        id: "nx_alt_label",
        position: Cesium.Cartesian3.fromDegrees(aMid[0], aMid[1], 32),
        label: {
          text: `HAZARD-AWARE ALT · ${(
            result.hazardAwareRoute.distanceM / 1000
          ).toFixed(2)} km`,
          font: "700 11px sans-serif",
          fillColor: C("#ffedd5"),
          showBackground: true,
          backgroundColor: C("#7c2d12", 0.92),
          pixelOffset: new Cesium.Cartesian2(0, 18),
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
      });
    }
  }

  // 6. Origin (A) & Destination (B) Waypoint Pins
  if (origin) {
    routeDs.entities.add({
      id: "nx_origin_pin",
      position: Cesium.Cartesian3.fromDegrees(origin.lon, origin.lat, 16),
      point: {
        pixelSize: 15,
        color: C("#10b981", 1),
        outlineColor: C("#ecfdf5", 1),
        outlineWidth: 3,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
      label: {
        text: `A · ORIGIN\n${origin.label.slice(0, 32)}`,
        font: "700 11px sans-serif",
        fillColor: C("#ecfdf5"),
        showBackground: true,
        backgroundColor: C("#064e3b", 0.92),
        pixelOffset: new Cesium.Cartesian2(0, -28),
        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    });
  }

  if (destination) {
    routeDs.entities.add({
      id: "nx_destination_pin",
      position: Cesium.Cartesian3.fromDegrees(
        destination.lon,
        destination.lat,
        16
      ),
      point: {
        pixelSize: 15,
        color: C("#eab308", 1),
        outlineColor: C("#fefce8", 1),
        outlineWidth: 3,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
      label: {
        text: `B · DESTINATION\n${destination.label.slice(0, 32)}`,
        font: "700 11px sans-serif",
        fillColor: C("#fefce8"),
        showBackground: true,
        backgroundColor: C("#713f12", 0.92),
        pixelOffset: new Cesium.Cartesian2(0, -28),
        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    });
  }
}

export function fitViewerToRouteAnalysis(
  Cesium: any,
  viewer: any,
  params: {
    origin: RouteWaypoint | null;
    destination: RouteWaypoint | null;
    scenario: DisasterScenarioConfig;
    result: RouteComparisonResult | null;
    fallbackBounds: [number, number, number, number];
  }
): void {
  if (!viewer || !Cesium) return;
  const pts: [number, number][] = [];
  if (params.origin) pts.push([params.origin.lon, params.origin.lat]);
  if (params.destination) {
    pts.push([params.destination.lon, params.destination.lat]);
  }
  if (params.scenario.active) {
    for (const p of params.scenario.polygon) pts.push(p);
    if (params.scenario.center) pts.push(params.scenario.center);
  }
  if (params.result?.baselineRoute.path) {
    for (const p of params.result.baselineRoute.path) pts.push(p);
  }
  if (params.result?.hazardAwareRoute.path) {
    for (const p of params.result.hazardAwareRoute.path) pts.push(p);
  }

  let west: number, south: number, east: number, north: number;
  if (pts.length >= 2) {
    const lons = pts.map((p) => p[0]);
    const lats = pts.map((p) => p[1]);
    const spanLon = Math.max(0.006, Math.max(...lons) - Math.min(...lons));
    const spanLat = Math.max(0.006, Math.max(...lats) - Math.min(...lats));
    const padLon = spanLon * 0.32;
    const padLat = spanLat * 0.32;
    west = Math.min(...lons) - padLon;
    east = Math.max(...lons) + padLon;
    south = Math.min(...lats) - padLat;
    north = Math.max(...lats) + padLat;
  } else {
    [west, south, east, north] = params.fallbackBounds;
  }

  viewer.camera.flyTo({
    destination: Cesium.Rectangle.fromDegrees(west, south, east, north),
    orientation: {
      heading: 0,
      pitch: Cesium.Math.toRadians(-65),
      roll: 0,
    },
    duration: 1.1,
  });
}
