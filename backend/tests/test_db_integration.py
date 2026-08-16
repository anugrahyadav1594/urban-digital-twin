"""Integration tests: storage <-> engines. ARCHITECTURE §6, §12, §16, §22."""
from __future__ import annotations

import pytest

from conftest import requires_db
from app.core.config import get_settings
from app.engines.scenario import resolve_scenario
from app.repositories import (
    ResultsRepository, ScenarioRepository, SpatialRepository,
)
from app.services import AnalysisService, PlanningService, ScenarioService
from app.storage.db import check_connection


# ---------------- connectivity ----------------
@requires_db
def test_postgis_available():
    info = check_connection()
    assert info["connected"]
    assert info["postgis"]
    assert info["missing_tables"] == []


@requires_db
def test_orm_matches_live_schema():
    from sqlalchemy import inspect
    from app.models import Base
    from app.storage.db import get_engine

    insp = inspect(get_engine())
    live = set(insp.get_table_names())
    for name, table in Base.metadata.tables.items():
        assert name in live, f"table {name} missing from database"
        cols = {c["name"] for c in insp.get_columns(name)}
        missing = set(table.columns.keys()) - cols
        assert not missing, f"{name}: ORM columns absent in DB: {missing}"


# ---------------- CRS boundary (§6.5) ----------------
@requires_db
def test_parcels_are_projected_not_degrees(session):
    parcels = SpatialRepository(session).parcels(limit=5)
    if not parcels:
        pytest.skip("no parcels seeded")
    p = parcels[0]
    # A degree-based area would be ~1e-6. Real parcels are thousands of m^2.
    assert p.area > 100.0, "geometry was not reprojected to the analysis CRS"
    assert abs(p.geometry.centroid.x) > 1000.0


@requires_db
def test_road_geometry_is_linestring(session):
    roads = SpatialRepository(session).roads(limit=5)
    if not roads:
        pytest.skip("no roads seeded")
    assert roads[0].geometry.geom_type in ("LineString", "MultiLineString")


@requires_db
def test_facility_geometry_coerced_to_point(session):
    facs = SpatialRepository(session).facilities(limit=5)
    if not facs:
        pytest.skip("no facilities seeded")
    assert all(f.geometry.geom_type == "Point" for f in facs)


# ---------------- column name translation ----------------
@requires_db
def test_schema_columns_map_to_engine_fields(session):
    parcels = SpatialRepository(session).parcels(limit=1)
    if not parcels:
        pytest.skip("no parcels seeded")
    p = parcels[0]
    # DB slope_deg -> engine .slope ; DB flood_risk -> engine .flood_risk
    assert hasattr(p, "slope") and hasattr(p, "flood_risk")


@requires_db
def test_severity_translation(session):
    cons = SpatialRepository(session).constraints()
    for c in cons:
        assert c.severity in ("hard", "soft")


# ---------------- spatial queries run in PostGIS ----------------
@requires_db
def test_nearby_facilities_uses_metre_radius(session):
    repo = SpatialRepository(session)
    ext = repo.city_extent()
    if ext is None:
        pytest.skip("no data")
    lon = (ext[0] + ext[2]) / 2
    lat = (ext[1] + ext[3]) / 2
    near = repo.nearby_facilities(lon, lat, radius_m=5000)
    for f in near:
        assert f["distance_m"] <= 5000.0
    assert near == sorted(near, key=lambda x: x["distance_m"])


# ---------------- graph connectivity (regression) ----------------
@requires_db
def test_road_graph_is_connected(session):
    import networkx as nx
    from app.engines.network import build_graph

    roads = SpatialRepository(session).roads()
    if len(roads) < 4:
        pytest.skip("not enough roads")
    G = build_graph(roads)
    comps = list(nx.connected_components(G.to_undirected()))
    largest = max(len(c) for c in comps) / G.number_of_nodes()
    # Regression guard: unnoded crossings previously left every road isolated.
    assert largest > 0.5, f"road graph fragmented into {len(comps)} components"


# ---------------- scenario invariant (§16) ----------------
@requires_db
def test_scenario_never_mutates_base_city(session):
    repo = SpatialRepository(session)
    scen = ScenarioRepository(session)
    parcels = repo.parcels(limit=1)
    if not parcels:
        pytest.skip("no parcels")
    pid = parcels[0].id
    original = parcels[0].zoning

    sid = scen.create("invariant probe")
    scen.add_change(sid, "parcel", "UPDATE",
                    {"zoning": "SENTINEL-DO-NOT-PERSIST"}, object_id=int(pid))
    session.commit()

    city = resolve_scenario({"parcels": repo.parcels()},
                            scen.to_engine_changes(sid), 1, str(sid), 1)
    in_scenario = [p for p in city.parcels if p.id == pid][0].zoning
    session.expire_all()
    after = [p for p in repo.parcels() if p.id == pid][0].zoning

    assert in_scenario == "SENTINEL-DO-NOT-PERSIST"
    assert after == original, "base city was mutated by a scenario"


@requires_db
def test_operation_vocabulary_translated(session):
    scen = ScenarioRepository(session)
    sid = scen.create("vocab probe")
    scen.add_change(sid, "facility", "INSERT",
                    {"type": "clinic",
                     "geometry": {"type": "Point", "coordinates": [73.14, 19.0]}})
    session.commit()
    changes = scen.to_engine_changes(sid)
    assert changes[0].operation == "add"
    assert changes[0].entity_type == "facility"


# ---------------- results persistence (§22) ----------------
@requires_db
def test_result_roundtrip_preserves_provenance(session):
    out = PlanningService(session).find_sites("hospital", top_n=2)
    rid = out["result_id"]
    fetched = ResultsRepository(session).get(rid)
    assert fetched is not None
    prov = fetched["result"]["provenance"]
    for key in ("dataset_version", "algorithm_version", "parameters",
                "parameter_hash", "analysis_srid"):
        assert key in prov


@requires_db
def test_idempotency_hash_lookup(session):
    out = PlanningService(session).find_sites("school", top_n=1)
    h = out["provenance"]["parameter_hash"]
    hit = ResultsRepository(session).find_by_parameter_hash(h)
    assert hit is not None and hit["id"] == out["result_id"]


# ---------------- services ----------------
@requires_db
def test_site_suitability_rejections_are_explained(session):
    out = PlanningService(session).find_sites(
        "hospital", top_n=3, required_area=5000, max_flood_risk=0.25)
    metrics = {m["name"]: m["value"] for m in out["metrics"]}
    assert metrics["parcels_evaluated"] > 0
    for rec in out["records"]:
        assert "criteria" in rec and "score" in rec and "rank" in rec


@requires_db
def test_accessibility_reports_units(session):
    out = AnalysisService(session).accessibility("hospital", 900)
    if "error" in out:
        pytest.skip(out["error"])
    for m in out["metrics"]:
        assert m["unit"], f"metric {m['name']} has no unit"


@requires_db
def test_scenario_comparison_ranks(session):
    sv = ScenarioService(session)
    a = sv.create("cmp A")["scenario_id"]
    sv.add_change(a, "facility", "INSERT",
                  {"type": "hospital", "capacity": 300,
                   "geometry": {"type": "Point", "coordinates": [73.135, 18.995]}})
    b = sv.create("cmp B")["scenario_id"]
    sv.add_change(b, "facility", "INSERT",
                  {"type": "hospital", "capacity": 300,
                   "geometry": {"type": "Point", "coordinates": [73.147, 19.002]}})
    out = sv.compare([a, b])
    ranks = [r["rank"] for r in out["records"]]
    assert sorted(ranks) == [1, 2]
