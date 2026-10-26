import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  STUDY_AREAS,
  buildRoadGraph,
  buildSyntheticBenchmarkDataset,
  compareRoutesOnGraph,
  createPresetScenarios,
  validateHazardPolygon,
} from "../lib/routing-engine.ts";
import { useRouteAnalysisStore } from "../stores/route-analysis-store.ts";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PANVEL_JSON_PATH = path.resolve(
  __dirname,
  "../public/data/panvel-osm-demo.json"
);

test("Bundled OpenStreetMap study-area network builds connected graph and routes accurately", () => {
  const raw = JSON.parse(fs.readFileSync(PANVEL_JSON_PATH, "utf-8"));
  const graph = buildRoadGraph(raw.roads);

  assert.ok(
    graph.routableCore.size > 2000,
    `Expected >2000 connected OSM nodes, got ${graph.routableCore.size}`
  );
  assert.ok(graph.edges.length > 4000);

  const studyArea = STUDY_AREAS.panvel_kalundre_osm;
  const presets = createPresetScenarios();

  // 1. Control scenario (hazard inactive): baseline & hazard-aware match identically
  const control = presets.find((p) => p.id === "preset_baseline_control")!;
  const resControl = compareRoutesOnGraph({
    graph,
    studyArea,
    origin: studyArea.defaultOrigin,
    destination: studyArea.defaultDestination,
    scenario: control,
    costMetric: "time",
    dataMode: "demo",
  });
  assert.equal(resControl.baselineRoute.feasible, true);
  assert.equal(resControl.hazardAwareRoute.feasible, true);
  assert.equal(resControl.comparison.routesIdentical, true);
  assert.equal(resControl.baselineRoute.exposedDistanceM, 0);
  assert.equal(resControl.hazardAwareRoute.exposedDistanceM, 0);

  // 2. Demonstration Flood Scenario: closes lower Kalundre bridge, inducing upstream detour
  const flood = presets.find((p) => p.id === "preset_kalundre_flood")!;
  const resFlood = compareRoutesOnGraph({
    graph,
    studyArea,
    origin: studyArea.defaultOrigin,
    destination: studyArea.defaultDestination,
    scenario: flood,
    costMetric: "time",
    dataMode: "demo",
  });
  assert.equal(resFlood.baselineRoute.feasible, true);
  assert.equal(resFlood.hazardAwareRoute.feasible, true);
  assert.equal(resFlood.comparison.routesIdentical, false);
  assert.ok(resFlood.baselineRoute.affectedSegmentCount > 0);
  assert.ok(resFlood.baselineRoute.exposedDistanceM > 0);
  assert.equal(resFlood.hazardAwareRoute.exposedDistanceM, 0);
  assert.ok(
    (resFlood.hazardAwareRoute.distanceM ?? 0) >
      (resFlood.baselineRoute.distanceM ?? 0)
  );

  // 3. Multi-bridge river severance: reports honest unreachable state
  const severance = presets.find((p) => p.id === "preset_river_severance")!;
  const resSeverance = compareRoutesOnGraph({
    graph,
    studyArea,
    origin: studyArea.defaultOrigin,
    destination: studyArea.defaultDestination,
    scenario: severance,
    costMetric: "time",
    dataMode: "demo",
  });
  assert.equal(resSeverance.baselineRoute.feasible, true);
  assert.equal(resSeverance.hazardAwareRoute.feasible, false);
  assert.equal(resSeverance.hazardAwareRoute.path.length, 0);
  assert.match(
    resSeverance.comparison.summary,
    /No feasible route found under the current scenario/
  );
});

test("Synthetic 7x7 benchmark planarizes crossings, respects penalty trade-offs, and validates inputs", () => {
  const ds = buildSyntheticBenchmarkDataset();
  assert.equal(ds.nodeCount, 49);
  assert.equal(ds.directedEdgeCount, 168);

  const graph = buildRoadGraph(ds.roads);
  const studyArea = STUDY_AREAS.pilot_synthetic_grid;
  const presets = createPresetScenarios();
  const basePen = presets.find((p) => p.id === "preset_grid_penalty")!;

  // Deterministic repeatability
  const r1 = compareRoutesOnGraph({
    graph,
    studyArea,
    origin: studyArea.defaultOrigin,
    destination: studyArea.defaultDestination,
    scenario: basePen,
    costMetric: "time",
    dataMode: "demo",
  });
  const r2 = compareRoutesOnGraph({
    graph,
    studyArea,
    origin: studyArea.defaultOrigin,
    destination: studyArea.defaultDestination,
    scenario: basePen,
    costMetric: "time",
    dataMode: "demo",
  });
  assert.deepEqual(r1.baselineRoute, r2.baselineRoute);
  assert.deepEqual(r1.hazardAwareRoute, r2.hazardAwareRoute);

  // Invalid inputs rejected
  assert.throws(
    () =>
      compareRoutesOnGraph({
        graph,
        studyArea,
        origin: studyArea.defaultOrigin,
        destination: studyArea.defaultOrigin,
        scenario: basePen,
        costMetric: "time",
        dataMode: "demo",
      }),
    /same road intersection/
  );

  assert.throws(
    () =>
      compareRoutesOnGraph({
        graph,
        studyArea,
        origin: studyArea.defaultOrigin,
        destination: studyArea.defaultDestination,
        scenario: { ...basePen, penaltyMultiplier: 0.4 },
        costMetric: "time",
        dataMode: "demo",
      }),
    /penalty multiplier/i
  );

  // Polygon validation catches too-few vertices and self-intersections
  assert.ok(validateHazardPolygon([[73.13, 18.99], [73.14, 18.99]]) !== null);
  assert.ok(
    validateHazardPolygon([
      [73.13, 18.99],
      [73.14, 19.0],
      [73.13, 19.0],
      [73.14, 18.99],
    ]) !== null
  );
  assert.equal(
    validateHazardPolygon([
      [73.13, 18.99],
      [73.14, 18.99],
      [73.14, 19.0],
      [73.13, 19.0],
    ]),
    null
  );
});

test("Route workflow store handles waypoints, polygon drawing, stale-result detection, resetDemo, and live API contracts", async () => {
  const panvelJson = JSON.parse(fs.readFileSync(PANVEL_JSON_PATH, "utf-8"));
  const originalFetch = globalThis.fetch;

  try {
    // Mock fetch for local static asset + live API tests
    globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/data/panvel-osm-demo.json")) {
        return new Response(JSON.stringify(panvelJson), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      if (url.endsWith("/ready")) {
        return new Response(JSON.stringify({ ready: false }), { status: 503 });
      }
      if (url.endsWith("/emergency/route-compare")) {
        const reqBody = JSON.parse(String(init?.body ?? "{}"));
        if (reqBody.scenario?.name === "TRIGGER_503") {
          return new Response(
            JSON.stringify({ detail: "PostGIS database unavailable" }),
            { status: 503, headers: { "content-type": "application/json" } }
          );
        }
        return new Response(
          JSON.stringify({
            baseline_route: {
              feasible: true,
              path: [
                [reqBody.origin.lon, reqBody.origin.lat],
                [reqBody.destination.lon, reqBody.destination.lat],
              ],
              distance_m: 1236.0,
              travel_time_s: 128.0,
              segment_count: 6,
              affected_segment_count: 2,
              affected_road_ids: ["osm_way_459498364"],
              exposed_distance_m: 118.0,
              snap_origin_m: 5.0,
              snap_destination_m: 7.0,
            },
            hazard_aware_route: {
              feasible: true,
              path: [
                [reqBody.origin.lon, reqBody.origin.lat],
                [73.1301, 18.9944],
                [reqBody.destination.lon, reqBody.destination.lat],
              ],
              distance_m: 2479.0,
              travel_time_s: 265.0,
              segment_count: 14,
              affected_segment_count: 0,
              affected_road_ids: [],
              exposed_distance_m: 0.0,
              snap_origin_m: 5.0,
              snap_destination_m: 7.0,
            },
            affected_network: {
              closed_edge_count: 4,
              penalized_edge_count: 0,
              closed_road_ids: ["osm_way_459498364"],
              penalized_road_ids: [],
              closed_segments: [],
              penalized_segments: [],
            },
            comparison: {
              baseline_feasible: true,
              alternative_feasible: true,
              routes_identical: false,
              distance_delta_m: 1243.0,
              distance_delta_pct: 100.6,
              time_delta_s: 137.0,
              time_delta_pct: 107.0,
              avoided_segments: 2,
              exposure_reduction_m: 118.0,
              summary: "Live backend detour avoids lower bridge.",
              assumptions: ["Dijkstra"],
              limitations: ["Simulated hazard"],
              warnings: [],
            },
            computation_time_ms: 3.1,
            provenance: {
              data_mode: "live_postgis",
              execution_engine: "backend_networkx_dijkstra",
              algorithm: "network.disaster_route_compare",
              dataset_version: 1,
            },
          }),
          { status: 200, headers: { "content-type": "application/json" } }
        );
      }
      throw new Error(`Unexpected fetch URL in test: ${url}`);
    };

    const store = useRouteAnalysisStore;
    await store.getState().resetDemo();

    assert.equal(store.getState().studyAreaId, "panvel_kalundre_osm");
    assert.equal(store.getState().dataMode, "demo");
    assert.ok(store.getState().affectedPreview !== null);

    // Run demo flood route analysis
    await store.getState().runRouteAnalysis();
    const firstResult = store.getState().result;
    assert.equal(store.getState().analysisStatus, "success");
    assert.ok(firstResult !== null);
    assert.equal(firstResult.provenance.dataMode, "demo");
    assert.equal(store.getState().rightPanelOpen, true);
    assert.equal(store.getState().wizardStep, 6);
    assert.equal(store.getState().isResultStale(), false);

    // Interactive map click for Origin marks existing result as stale
    store.getState().setInteractionMode("pick_origin");
    store.getState().handleMapCoordinateClick(73.12268, 18.99187);
    assert.equal(store.getState().interactionMode, "navigate");
    assert.equal(store.getState().isResultStale(), true);

    // Interactive polygon drawing validation & completion
    store.getState().setInteractionMode("draw_hazard_polygon");
    store.getState().handleMapCoordinateClick(73.128, 18.986);
    store.getState().handleMapCoordinateClick(73.13, 18.986);
    assert.equal(store.getState().finishDrawingPolygon().ok, false);
    store.getState().handleMapCoordinateClick(73.13, 18.988);
    store.getState().handleMapCoordinateClick(73.128, 18.988);
    assert.equal(store.getState().finishDrawingPolygon().ok, true);
    assert.equal(store.getState().draftScenario.polygon.length, 4);

    // Live mode contract success
    store.getState().setDataMode("live");
    await store.getState().runRouteAnalysis();
    assert.equal(store.getState().analysisStatus, "success");
    assert.equal(store.getState().result?.provenance.dataMode, "live");
    assert.equal(store.getState().result?.hazardAwareRoute.distanceM, 2479);

    // Live mode failure does NOT silently masquerade as a live or demo result
    store.getState().updateDraftScenario({ name: "TRIGGER_503" });
    await store.getState().runRouteAnalysis();
    assert.equal(store.getState().analysisStatus, "error");
    assert.match(store.getState().analysisError ?? "", /PostGIS database unavailable/);

    // Reset demo restores clean state
    await store.getState().resetDemo();
    assert.equal(store.getState().result, null);
    assert.equal(store.getState().analysisStatus, "idle");
    assert.equal(store.getState().wizardStep, 1);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
