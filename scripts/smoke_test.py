"""End-to-end smoke test: DB -> repositories -> engines -> DB.

    python scripts/smoke_test.py

Exercises the real wiring in one pass and prints a human-readable report.
Exit code 0 means the backend and database work together.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

PASS, FAIL = "  [PASS] ", "  [FAIL] "
_failures: list[str] = []


def step(title: str):
    print(f"\n--- {title} " + "-" * max(0, 56 - len(title)))


def check(label: str, condition: bool, detail: str = "") -> bool:
    print((PASS if condition else FAIL) + label + (f"  {detail}" if detail else ""))
    if not condition:
        _failures.append(label)
    return condition


def main() -> int:
    print("=" * 68)
    print("  BACKEND <-> DATABASE SMOKE TEST")
    print("=" * 68)

    from app.core.config import get_settings
    from app.storage.db import check_connection, session_scope

    cfg = get_settings()

    # 1 -------------------------------------------------- connectivity
    step("1. Connectivity")
    info = check_connection()
    err = (info.get("error") or "").strip().splitlines()
    # The driver error is a 30-line wall; the first line carries the cause.
    first = next((l for l in err if l.strip()), "")
    if not check("database reachable", info["connected"], first):
        print("\n  Run: python -m app.storage.doctor\n")
        return 1
    check("PostGIS installed", bool(info["postgis"]), info["postgis"])
    check("all core tables present", not info["missing_tables"],
          f"{info['tables_present']}/11")

    with session_scope() as s:
        from app.repositories import (
            ResultsRepository, ScenarioRepository, SpatialRepository)
        from app.services import AnalysisService, PlanningService, ScenarioService

        repo = SpatialRepository(s)

        # 2 ---------------------------------------------- data present
        step("2. Seeded data")
        counts = repo.counts()
        for name in ("roads", "facilities", "land_parcels", "population_zones"):
            check(f"{name:20s} {counts.get(name, 0):>5d} rows", counts.get(name, 0) > 0)
        if not all(counts.get(n, 0) for n in ("roads", "land_parcels")):
            print("\n  Empty database. Run: python db/seed_demo.py\n")
            return 1

        # 3 ---------------------------------------------- CRS boundary
        step("3. CRS boundary (4326 stored -> projected for analysis)")
        parcels = repo.parcels(limit=1)
        area = parcels[0].area
        check("parcel area is in square metres", area > 100,
              f"{area:,.1f} m^2")
        check("geometry is projected, not degrees",
              abs(parcels[0].geometry.centroid.x) > 1000,
              f"centroid x = {parcels[0].geometry.centroid.x:,.0f}")
        ext = repo.city_extent()
        check("extent returned in lon/lat", ext is not None and -180 <= ext[0] <= 180,
              f"{tuple(round(v, 3) for v in ext)}" if ext else "")

        # 4 ---------------------------------------------- graph
        step("4. Road network graph")
        import networkx as nx
        from app.engines.network import build_graph
        G = build_graph(repo.roads())
        ncomp = nx.number_connected_components(G.to_undirected())
        check("graph built", G.number_of_nodes() > 0,
              f"{G.number_of_nodes()} nodes / {G.number_of_edges()} edges")
        check("network is connected", ncomp == 1,
              f"{ncomp} component(s)" +
              ("" if ncomp == 1 else "  <-- roads do not meet; check graph_builder fix"))

        # 5 ---------------------------------------------- planning
        step("5. Site suitability (§14)")
        out = PlanningService(s).find_sites("hospital", top_n=3)
        m = {x["name"]: x["value"] for x in out["metrics"]}
        check("parcels evaluated", m.get("parcels_evaluated", 0) > 0,
              str(int(m.get("parcels_evaluated", 0))))
        check("ranked sites returned", len(out["records"]) > 0,
              " ".join(f"#{r['rank']} parcel {r['parcel_id']} ({r['score']:.3f})"
                       for r in out["records"][:3]))
        check("result persisted with id", bool(out.get("result_id")),
              f"result_id={out.get('result_id')}")
        check("provenance hash recorded",
              bool(out["provenance"].get("parameter_hash")),
              out["provenance"].get("parameter_hash", ""))

        # 6 ---------------------------------------------- analysis
        step("6. Accessibility (§13)")
        acc = AnalysisService(s).accessibility("hospital", 900)
        am = {x["name"]: x["value"] for x in acc.get("metrics", [])}
        cov = am.get("coverage_ratio")
        check("coverage computed", cov is not None, f"{cov}")
        check("population is routable", (am.get("population_unreachable", 1) == 0),
              f"unreachable = {am.get('population_unreachable')}")
        check("mean travel time is finite",
              isinstance(am.get("mean_travel_time"), (int, float)),
              f"{am.get('mean_travel_time')} s")

        # 7 ---------------------------------------------- scenario
        step("7. Scenario isolation (§16)")
        sv = ScenarioService(s)
        sid = sv.create("smoke-test scenario")["scenario_id"]
        sv.add_change(sid, "facility", "INSERT",
                      {"type": "hospital", "capacity": 250,
                       "geometry": {"type": "Point", "coordinates": [73.138, 18.997]}})
        before = len(repo.facilities())
        city = sv.resolve(sid)
        s.expire_all()
        after = len(repo.facilities())
        check("delta applied in memory", len(city.facilities) == before + 1,
              f"{before} -> {len(city.facilities)}")
        check("base city UNCHANGED in database", after == before,
              f"{after} facilities still stored")
        check("no changes rejected", not city.rejected, str(city.rejected))

        # 8 ---------------------------------------------- results
        step("8. Result retrieval (§22)")
        rr = ResultsRepository(s)
        fetched = rr.get(out["result_id"])
        check("result reloads from database", fetched is not None)
        if fetched:
            check("provenance survived the round trip",
                  "parameter_hash" in fetched["result"]["provenance"])
        hit = rr.find_by_parameter_hash(out["provenance"]["parameter_hash"])
        check("idempotency lookup by hash works", hit is not None,
              f"id={hit['id']}" if hit else "")

    # ------------------------------------------------------ verdict
    print("\n" + "=" * 68)
    if _failures:
        print(f"  {len(_failures)} CHECK(S) FAILED")
        for f in _failures:
            print(f"    - {f}")
        print("=" * 68 + "\n")
        return 1
    print("  ALL CHECKS PASSED - backend and database are working together")
    print(f"  analysis CRS EPSG:{cfg.analysis_srid} | storage EPSG:{cfg.storage_srid}")
    print("=" * 68 + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        print("\n  Unexpected error. Run: python -m app.storage.doctor\n")
        sys.exit(2)
