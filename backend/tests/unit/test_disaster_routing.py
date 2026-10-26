"""Unit and API contract tests for disaster-aware point-to-point route comparison."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from shapely.geometry import LineString, Point, Polygon

from app.api.deps import get_emergency_service
from app.engines.contracts import Road
from app.engines.network.disaster_routing import (
    DisasterScenarioSpec,
    compare_disaster_routes,
)
from app.engines.network.graph_builder import build_graph
from app.main import app


def _make_grid_roads() -> list[Road]:
    """Construct a planar 3x3 metric road grid (0 m, 500 m, 1000 m) with a fast central bridge."""
    roads: list[Road] = []
    coords = [0.0, 500.0, 1000.0]
    # Horizontal segments
    for row_idx, y in enumerate(coords):
        for col_idx in range(2):
            x0, x1 = coords[col_idx], coords[col_idx + 1]
            is_central = row_idx == 1
            roads.append(
                Road(
                    id=f"h_{row_idx}_{col_idx}",
                    road_class="primary" if is_central else "residential",
                    speed=50.0 if is_central else 25.0,
                    oneway=False,
                    geometry=LineString([(x0, y), (x1, y)]),
                )
            )
    # Vertical segments
    for col_idx, x in enumerate(coords):
        for row_idx in range(2):
            y0, y1 = coords[row_idx], coords[row_idx + 1]
            roads.append(
                Road(
                    id=f"v_{col_idx}_{row_idx}",
                    road_class="secondary",
                    speed=35.0,
                    oneway=False,
                    geometry=LineString([(x, y0), (x, y1)]),
                )
            )
    return roads


def test_baseline_and_inactive_hazard_match():
    G = build_graph(_make_grid_roads(), mode="car")
    spec = DisasterScenarioSpec(
        name="Inactive Control",
        scenario_type="flood",
        active=False,
        severity_mode="closed",
        affected_road_ids=("h_1_0", "h_1_1"),
    )
    res = compare_disaster_routes(
        G, Point(0.0, 500.0), Point(1000.0, 500.0), spec, cost_metric="time"
    )
    assert res["baseline_route"]["feasible"] is True
    assert res["hazard_aware_route"]["feasible"] is True
    assert res["comparison"]["routes_identical"] is True
    assert res["baseline_route"]["distance_m"] == 1000.0
    assert res["baseline_route"]["exposed_distance_m"] == 0.0
    assert res["hazard_aware_route"]["exposed_distance_m"] == 0.0


def test_closed_polygon_hazard_induces_detour_and_eliminates_exposure():
    G = build_graph(_make_grid_roads(), mode="car")
    # Flood polygon covering the central horizontal corridor around (500, 500)
    flood_poly = Polygon([(200.0, 450.0), (800.0, 450.0), (800.0, 550.0), (200.0, 550.0)])
    spec = DisasterScenarioSpec(
        name="Central Corridor Flood",
        scenario_type="flood",
        active=True,
        severity_mode="closed",
        hazard_geometry=flood_poly,
    )
    res = compare_disaster_routes(
        G, Point(0.0, 500.0), Point(1000.0, 500.0), spec, cost_metric="distance"
    )
    base = res["baseline_route"]
    alt = res["hazard_aware_route"]
    comp = res["comparison"]

    assert base["feasible"] is True
    assert alt["feasible"] is True
    assert comp["routes_identical"] is False
    # Baseline goes straight across y=500 (1000 m, both central segments exposed)
    assert base["distance_m"] == 1000.0
    assert base["affected_segment_count"] == 2
    assert base["exposed_distance_m"] == 1000.0
    # Alternative detours via y=0 or y=1000 (500 up/down + 1000 across + 500 back = 2000 m)
    assert alt["distance_m"] == 2000.0
    assert alt["affected_segment_count"] == 0
    assert alt["exposed_distance_m"] == 0.0
    assert comp["distance_delta_m"] == 1000.0
    assert comp["exposure_reduction_m"] == 1000.0


def test_penalized_segment_tradeoff():
    G = build_graph(_make_grid_roads(), mode="car")
    # Mild 1.1x distance penalty on 1000 m central corridor -> effective 1100 m < 2000 m detour
    mild = DisasterScenarioSpec(
        name="Mild Slowdown",
        scenario_type="affected_zone",
        active=True,
        severity_mode="penalized",
        penalty_multiplier=1.1,
        affected_road_ids=("h_1_0", "h_1_1"),
    )
    res_mild = compare_disaster_routes(
        G, Point(0.0, 500.0), Point(1000.0, 500.0), mild, cost_metric="distance"
    )
    assert res_mild["comparison"]["routes_identical"] is True
    assert res_mild["hazard_aware_route"]["exposed_distance_m"] == 1000.0

    # Severe 3.0x distance penalty on 1000 m central corridor -> effective 3000 m > 2000 m detour
    severe = DisasterScenarioSpec(
        name="Severe Slowdown",
        scenario_type="affected_zone",
        active=True,
        severity_mode="penalized",
        penalty_multiplier=3.0,
        affected_road_ids=("h_1_0", "h_1_1"),
    )
    res_severe = compare_disaster_routes(
        G, Point(0.0, 500.0), Point(1000.0, 500.0), severe, cost_metric="distance"
    )
    assert res_severe["comparison"]["routes_identical"] is False
    assert res_severe["hazard_aware_route"]["distance_m"] == 2000.0
    assert res_severe["hazard_aware_route"]["exposed_distance_m"] == 0.0


def test_unreachable_destination_reports_no_feasible_route():
    G = build_graph(_make_grid_roads(), mode="car")
    # Block every horizontal link crossing from x=0..500 to x=500..1000
    spec = DisasterScenarioSpec(
        name="Full River Severance",
        scenario_type="flood",
        active=True,
        severity_mode="closed",
        affected_road_ids=("h_0_1", "h_1_1", "h_2_1"),
    )
    res = compare_disaster_routes(
        G, Point(0.0, 500.0), Point(1000.0, 500.0), spec, cost_metric="time"
    )
    assert res["baseline_route"]["feasible"] is True
    assert res["hazard_aware_route"]["feasible"] is False
    assert res["hazard_aware_route"]["path"] == []
    assert res["hazard_aware_route"]["distance_m"] is None
    assert "No feasible route found under the current scenario" in res["comparison"]["summary"]


def test_invalid_inputs_rejected():
    G = build_graph(_make_grid_roads(), mode="car")
    # Negative / <1.0 penalty multiplier
    with pytest.raises(ValueError, match="penalty multiplier"):
        compare_disaster_routes(
            G,
            Point(0.0, 0.0),
            Point(1000.0, 1000.0),
            DisasterScenarioSpec(name="Bad", penalty_multiplier=0.5),
        )
    # Identical origin and destination node
    with pytest.raises(ValueError, match="same road intersection"):
        compare_disaster_routes(
            G,
            Point(0.0, 0.0),
            Point(2.0, 2.0),
            DisasterScenarioSpec(name="Same Node"),
        )
    # Out-of-bounds snap distance
    with pytest.raises(ValueError, match="nearest road"):
        compare_disaster_routes(
            G,
            Point(-10000.0, -10000.0),
            Point(1000.0, 1000.0),
            DisasterScenarioSpec(name="Far Origin"),
        )


def test_deterministic_repeatability():
    G = build_graph(_make_grid_roads(), mode="car")
    spec = DisasterScenarioSpec(
        name="Road Blockage",
        scenario_type="road_blockage",
        active=True,
        severity_mode="closed",
        affected_road_ids=("h_1_0",),
    )
    r1 = compare_disaster_routes(G, Point(0.0, 500.0), Point(1000.0, 500.0), spec)
    r2 = compare_disaster_routes(G, Point(0.0, 500.0), Point(1000.0, 500.0), spec)
    assert r1["baseline_route"] == r2["baseline_route"]
    assert r1["hazard_aware_route"] == r2["hazard_aware_route"]
    assert r1["comparison"]["distance_delta_m"] == r2["comparison"]["distance_delta_m"]


def test_route_compare_endpoint_contract():
    class StubEmergencyService:
        def compare_od_routes(self, **kwargs):
            if kwargs["origin_lon"] == kwargs["destination_lon"] and kwargs["origin_lat"] == kwargs["destination_lat"]:
                raise ValueError("Origin and destination map to the same road intersection.")
            return {
                "baseline_route": {
                    "feasible": True,
                    "path": [[kwargs["origin_lon"], kwargs["origin_lat"]], [kwargs["destination_lon"], kwargs["destination_lat"]]],
                    "distance_m": 1250.0,
                    "travel_time_s": 140.0,
                    "segment_count": 4,
                    "affected_segment_count": 2,
                    "affected_road_ids": ["osm_way_1"],
                    "exposed_distance_m": 320.0,
                    "snap_origin_m": 8.2,
                    "snap_destination_m": 11.4,
                },
                "hazard_aware_route": {
                    "feasible": True,
                    "path": [[kwargs["origin_lon"], kwargs["origin_lat"]], [73.135, 19.001], [kwargs["destination_lon"], kwargs["destination_lat"]]],
                    "distance_m": 1780.0,
                    "travel_time_s": 195.0,
                    "segment_count": 7,
                    "affected_segment_count": 0,
                    "affected_road_ids": [],
                    "exposed_distance_m": 0.0,
                    "snap_origin_m": 8.2,
                    "snap_destination_m": 11.4,
                },
                "affected_network": {
                    "closed_edge_count": 4,
                    "penalized_edge_count": 0,
                    "closed_road_ids": ["osm_way_1"],
                    "penalized_road_ids": [],
                    "closed_segments": [],
                    "penalized_segments": [],
                },
                "comparison": {
                    "baseline_feasible": True,
                    "alternative_feasible": True,
                    "routes_identical": False,
                    "distance_delta_m": 530.0,
                    "distance_delta_pct": 42.4,
                    "time_delta_s": 55.0,
                    "time_delta_pct": 39.3,
                    "avoided_segments": 2,
                    "exposure_reduction_m": 320.0,
                    "summary": "Detour avoids 320 m of simulated exposure.",
                    "assumptions": [],
                    "limitations": [],
                    "warnings": [],
                },
                "computation_time_ms": 2.4,
                "provenance": {
                    "data_mode": "live_postgis",
                    "execution_engine": "backend_networkx_dijkstra",
                    "algorithm": "network.disaster_route_compare",
                },
            }

    app.dependency_overrides[get_emergency_service] = lambda: StubEmergencyService()
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/emergency/route-compare",
            json={
                "origin": {"lon": 73.12664, "lat": 18.99947},
                "destination": {"lon": 73.14058, "lat": 19.0019},
                "scenario": {
                    "name": "Kalundre Flood",
                    "type": "flood",
                    "active": True,
                    "severity_mode": "closed",
                    "penalty_multiplier": 3.0,
                    "affected_road_ids": ["osm_way_1"],
                },
                "cost_metric": "time",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["baseline_route"]["distance_m"] == 1250.0
        assert body["hazard_aware_route"]["distance_m"] == 1780.0
        assert body["provenance"]["data_mode"] == "live_postgis"

        bad = client.post(
            "/api/v1/emergency/route-compare",
            json={
                "origin": {"lon": 73.13, "lat": 19.0},
                "destination": {"lon": 73.13, "lat": 19.0},
            },
        )
        assert bad.status_code == 422
    finally:
        app.dependency_overrides.pop(get_emergency_service, None)
