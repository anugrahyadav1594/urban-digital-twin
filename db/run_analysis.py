"""CLI to run engine analyses against the live PostGIS database.

ARCHITECTURE §5, §22.

Usage (from the db/ directory):
    python run_analysis.py selftest
    python run_analysis.py suitability --facility hospital --top 5
    python run_analysis.py accessibility --facility hospital --minutes 15
    python run_analysis.py emergency --facility fire_station --minutes 8
    python run_analysis.py capacity --facility hospital
    python run_analysis.py resilience
    python run_analysis.py service-area --lat 18.995 --lon 73.135 --minutes 10
    python run_analysis.py optimize --n 2 --objective p_median
    python run_analysis.py scenario --id 2
    python run_analysis.py compare --ids 2,3
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from db_config import get_engine, test_db_connection      # noqa: E402

from db.services import (                                  # noqa: E402
    AnalysisContext, analyze_accessibility, analyze_capacity,
    analyze_emergency_response, analyze_resilience, compare,
    compute_service_area, evaluate_scenario, find_best_sites,
    optimize_facility_locations,
)


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


def selftest() -> int:
    """Verify adapters and engines without touching the database."""
    from shapely.geometry import MultiLineString, MultiPolygon, Point, box

    from db.adapters.geometry import (
        ANALYSIS_SRID, as_point, explode_lines, to_analysis,
    )
    from db.adapters.vocab import normalize_road_class, normalize_severity

    checks: list[tuple[str, bool]] = []

    mls = MultiLineString([[(0, 0), (1, 0)], [(50, 50), (60, 50)]])
    checks.append(("disjoint MultiLineString explodes to 2 parts",
                   len(explode_lines(mls)) == 2))
    checks.append(("severity HIGH -> hard", normalize_severity("HIGH") == "hard"))
    checks.append(("severity MEDIUM -> soft", normalize_severity("MEDIUM") == "soft"))
    checks.append(("unknown severity fails safe to hard",
                   normalize_severity("???") == "hard"))
    checks.append(("motorway_link -> motorway",
                   normalize_road_class("motorway_link") == "motorway"))
    checks.append(("polygon facility -> point",
                   as_point(box(0, 0, 10, 10)).geom_type == "Point"))

    p = to_analysis(Point(73.14, 19.0))
    checks.append((f"EPSG:{ANALYSIS_SRID} projection is metric",
                   300_000 < p.x < 320_000))

    from shapely.geometry import LineString

    from app.engines.contracts import Road
    from app.engines.network import build_graph

    roads = [
        Road(f"h{i}", to_analysis(LineString(
            [(73.130, 18.990 + i * 0.004), (73.150, 18.990 + i * 0.004)])),
            "primary")
        for i in range(4)
    ] + [
        Road(f"v{i}", to_analysis(LineString(
            [(73.130 + i * 0.005, 18.990), (73.130 + i * 0.005, 19.005)])),
            "primary")
        for i in range(4)
    ]
    G = build_graph(roads)
    import networkx as nx
    comps = list(nx.connected_components(G.to_undirected()))
    # 4x4 crossing grid: 16 interior junctions + 8 dangling ends = 24 nodes,
    # all in a single connected component once noding works.
    checks.append((
        f"reprojected 4x4 grid noded into one component "
        f"({G.number_of_nodes()} nodes, {len(comps)} component)",
        len(comps) == 1 and G.number_of_nodes() == 24,
    ))

    ok = True
    for label, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
        ok &= passed
    print("\nSELFTEST", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="NAGAR-X engine analysis runner")
    ap.add_argument("command", choices=[
        "selftest", "suitability", "accessibility", "emergency", "capacity",
        "resilience", "service-area", "optimize", "scenario", "compare",
    ])
    ap.add_argument("--facility", default="hospital")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--minutes", type=float, default=15.0)
    ap.add_argument("--area", type=float, default=5000.0)
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--n", type=int, default=2)
    ap.add_argument("--objective", default="p_median",
                    choices=["p_median", "max_coverage"])
    ap.add_argument("--id", type=int)
    ap.add_argument("--ids", type=str)
    ap.add_argument("--no-persist", action="store_true")
    args = ap.parse_args()

    if args.command == "selftest":
        return selftest()

    if not test_db_connection():
        print("[ERROR] database unavailable. Start PostgreSQL and run "
              "etl/run_full_etl.py first.")
        return 1

    engine = get_engine()
    ctx = AnalysisContext()
    persist = not args.no_persist

    if args.command == "suitability":
        _print(find_best_sites(engine, args.facility, ctx, top_n=args.top,
                               required_area=args.area, persist=persist))
    elif args.command == "accessibility":
        _print(analyze_accessibility(engine, args.facility, args.minutes, ctx, persist))
    elif args.command == "emergency":
        _print(analyze_emergency_response(engine, args.facility, args.minutes,
                                          ctx, persist))
    elif args.command == "capacity":
        _print(analyze_capacity(engine, args.facility, ctx, persist))
    elif args.command == "resilience":
        _print(analyze_resilience(engine, ctx, persist))
    elif args.command == "service-area":
        if args.lat is None or args.lon is None:
            print("[ERROR] --lat and --lon are required")
            return 1
        _print(compute_service_area(engine, args.lat, args.lon, args.minutes, ctx))
    elif args.command == "optimize":
        _print(optimize_facility_locations(
            engine, args.n, args.objective,
            args.minutes if args.objective == "max_coverage" else None,
            ctx=ctx, persist=persist))
    elif args.command == "scenario":
        if args.id is None:
            print("[ERROR] --id is required")
            return 1
        _print(evaluate_scenario(engine, args.id, args.facility, args.minutes,
                                 persist=persist))
    elif args.command == "compare":
        if not args.ids:
            print("[ERROR] --ids is required, e.g. --ids 2,3")
            return 1
        ids = [int(x) for x in args.ids.split(",")]
        _print(compare(engine, ids, args.facility, ctx, persist))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
