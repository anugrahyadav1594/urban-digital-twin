"""Regression tests for emergency responder routing, road graph filtering,
hazard edge blocking, mid-block snapping, and stress workflow coordinate updates.
"""
from __future__ import annotations

from unittest.mock import MagicMock
from shapely.geometry import LineString, Point, Polygon

from app.engines.contracts import Facility, Provenance, Road
from app.engines.network.emergency_routing import degrade_graph, route_to_incident
from app.engines.network.graph_builder import build_graph
from app.workflows.orchestrator import WorkflowOrchestrator
from app.workflows.schemas import (
    StressRerouteRequest,
    StressSimulateRequest,
    WorkflowId,
)


def _prov() -> Provenance:
    return Provenance(
        dataset_version=1,
        algorithm="emergency_routing_test",
        algorithm_version="1.0",
        analysis_srid=32643,
    )


def test_emergency_graph_excludes_non_vehicular_paths():
    """Emergency vehicles must never take footpaths, cycleways, tracks, or steps."""
    roads = [
        # Valid vehicular corridor around the block (0,0)->(0,300)->(400,300) = 700 m
        Road(
            id="r_arterial_1",
            geometry=LineString([(0.0, 0.0), (0.0, 300.0)]),
            road_class="primary",
            speed=50.0,
        ),
        Road(
            id="r_arterial_2",
            geometry=LineString([(0.0, 300.0), (400.0, 300.0)]),
            road_class="primary",
            speed=50.0,
        ),
        # Non-vehicular shortcuts that would be shorter if wrongly included
        Road(
            id="r_path",
            geometry=LineString([(0.0, 0.0), (400.0, 300.0)]),
            road_class="path",
            speed=20.0,
        ),
        Road(
            id="r_pedestrian",
            geometry=LineString([(0.0, 0.0), (200.0, 150.0), (400.0, 300.0)]),
            road_class="pedestrian",
            speed=20.0,
        ),
        Road(
            id="r_track",
            geometry=LineString([(0.0, 0.0), (400.0, 0.0), (400.0, 300.0)]),
            road_class="track",
            speed=20.0,
        ),
    ]

    G = build_graph(roads, mode="emergency", max_segment_m=25.0)
    stations = [
        Facility(
            id="fs_1",
            name="Central Fire Brigade",
            type="fire_station",
            geometry=Point(0.0, 0.0),
        )
    ]
    res = route_to_incident(G, Point(400.0, 300.0), stations, _prov(), top_n=1)
    assert len(res.records) == 1
    rec = res.records[0]
    assert rec["station_name"] == "Central Fire Brigade"
    # Must take the 700 m primary road corridor, never the 500 m diagonal footpath
    assert rec["distance_m"] >= 699.0
    assert len(rec["path"]) >= 3


def test_midblock_incident_snaps_accurately_with_segment_densification():
    """Mid-block incidents on long road chords snap within <=15m when max_segment_m=25."""
    roads = [
        Road(
            id="r_long",
            geometry=LineString([(0.0, 0.0), (500.0, 0.0)]),
            road_class="secondary",
            speed=40.0,
        )
    ]
    G = build_graph(roads, mode="emergency", max_segment_m=25.0)
    stations = [
        Facility(
            id="fs_west",
            name="West Station",
            type="fire_station",
            geometry=Point(0.0, 5.0),
        )
    ]
    # Incident at x=210m, y=6m (mid-block along the 500m segment)
    res = route_to_incident(G, Point(210.0, 6.0), stations, _prov(), top_n=1)
    rec = res.records[0]
    assert rec["staging_distance_m"] <= 15.0
    assert 195.0 <= rec["distance_m"] <= 235.0
    assert rec["station_location"] == [0.0, 5.0]
    assert rec["incident_location"] == [210.0, 6.0]


def test_same_node_snap_returns_valid_multipoint_path():
    """Station and incident snapping to the exact same vertex must still emit >=2 path points."""
    roads = [
        Road(
            id="r_1",
            geometry=LineString([(100.0, 100.0), (200.0, 100.0)]),
            road_class="residential",
            speed=30.0,
        )
    ]
    G = build_graph(roads, mode="emergency", max_segment_m=25.0)
    stations = [
        Facility(
            id="hosp_adjacent",
            name="Adjacent Clinic",
            type="hospital",
            geometry=Point(96.0, 104.0),
        )
    ]
    res = route_to_incident(G, Point(103.0, 95.0), stations, _prov(), top_n=1)
    assert len(res.records) == 1
    rec = res.records[0]
    assert len(rec["path"]) >= 2
    assert rec["distance_m"] > 0.0


def test_degrade_graph_blocks_edge_crossing_hazard_and_osm_source_ids():
    """Hazard crossing the interior of a bridge segment or matching osm_way_* source blocks it."""
    roads = [
        # Direct bridge across y=0 from x=0 to x=400 (endpoints outside flood polygon)
        Road(
            id="db_row_1",
            geometry=LineString([(0.0, 0.0), (400.0, 0.0)]),
            road_class="primary",
            speed=50.0,
            source="osm_way_999111",
        ),
        # Northern detour (0,0)->(0,200)->(400,200)->(400,0) = 800 m
        Road(
            id="db_row_2",
            geometry=LineString([(0.0, 0.0), (0.0, 200.0), (400.0, 200.0), (400.0, 0.0)]),
            road_class="secondary",
            speed=40.0,
            source="osm_way_999222",
        ),
    ]
    # Test without segment subdivision first so endpoints (0,0) and (400,0) lie outside hazard
    G = build_graph(roads, mode="emergency", node_network=False)
    hazard = Polygon([(150.0, -40.0), (250.0, -40.0), (250.0, 40.0), (150.0, 40.0)])
    Gd, stats = degrade_graph(G, blocked_geoms=[hazard])
    assert stats["blocked_by_geometry"] >= 1

    stations = [
        Facility(id="fs_1", name="West Fire", type="fire_station", geometry=Point(0.0, 0.0))
    ]
    res = route_to_incident(Gd, Point(400.0, 0.0), stations, _prov(), top_n=1)
    assert len(res.records) == 1
    # Detour is 800m instead of the flooded 400m bridge
    assert res.records[0]["distance_m"] >= 799.0

    # Also test explicit osm_way_* blocked_road_ids matching via Road.source
    Gd2, stats2 = degrade_graph(G, blocked_road_ids=["osm_way_999111"])
    assert stats2["blocked"] >= 1
    res2 = route_to_incident(Gd2, Point(400.0, 0.0), stations, _prov(), top_n=1)
    assert res2.records[0]["distance_m"] >= 799.0


def test_stress_reroute_honors_updated_incident_coordinates():
    """Stress workflow reroute must respect updated lon/lat instead of stale session coords."""
    orch = WorkflowOrchestrator(MagicMock())
    orch.emergency_svc.simulate_disaster = MagicMock(return_value={
        "persist_id": "res_sim_99",
        "baseline": {"population_at_risk": 2100},
        "mitigated": {"population_at_risk": 900},
        "network": {"blocked_ids": ["osm_way_999111"]},
    })
    orch.emergency_svc.calculate_emergency_route = MagicMock(return_value={
        "records": [{"station_id": "1", "response_time_min": 4.8, "rank": 1}]
    })

    start = orch.start_session(WorkflowId.STRESS, scenario_id=1)
    sid = start.session_id

    orch.stress_simulate(
        StressSimulateRequest(
            session_id=sid,
            hazard_type="flood",
            lon=73.135,
            lat=19.002,
        )
    )

    orch.stress_reroute(
        StressRerouteRequest(
            session_id=sid,
            responder_type="fire_station",
            lon=73.1215,
            lat=18.9942,
            turnout_seconds=75.0,
        )
    )
    orch.emergency_svc.calculate_emergency_route.assert_called_once()
    call_kwargs = orch.emergency_svc.calculate_emergency_route.call_args.kwargs
    assert call_kwargs["lon"] == 73.1215
    assert call_kwargs["lat"] == 18.9942
    assert call_kwargs["turnout_seconds"] == 75.0
    assert call_kwargs["blocked_road_ids"] == ["osm_way_999111"]
