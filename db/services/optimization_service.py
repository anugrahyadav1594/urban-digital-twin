"""Facility-location optimization over live PostGIS data.

ARCHITECTURE §15, §22.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.engine import Engine

from app.engines.network import build_graph
from app.engines.network.routing import travel_time_matrix
from app.engines.optimization import (
    FacilityLocationProblem, SolveOptions, solve_facility_location,
    solve_max_coverage,
)

from db.adapters.loaders import (
    load_parcels, load_population_zones, load_roads,
)
from db.adapters.writers import save_result

from .context import AnalysisContext

ALGORITHM_VERSION = "0.1.0"


def optimize_facility_locations(
    engine: Engine,
    n_facilities: int = 2,
    objective: str = "p_median",
    max_minutes: float | None = None,
    candidate_limit: int = 40,
    ctx: AnalysisContext | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Choose the best n parcels to open as facilities.

    objective: 'p_median' minimises population-weighted travel time;
               'max_coverage' maximises population within max_minutes.
    """
    ctx = ctx or AnalysisContext()

    parcels = load_parcels(engine, ctx.bbox, ctx.analysis_srid)
    zones = load_population_zones(engine, ctx.bbox, ctx.analysis_srid)
    roads = load_roads(engine, ctx.bbox, ctx.analysis_srid)

    if not parcels or not zones or not roads:
        return {"error": "parcels, population zones and roads are all required; "
                         "run the ETL pipeline first"}

    candidates = parcels[:candidate_limit]
    graph = build_graph(roads, mode="car")

    origins = [z.geometry.representative_point() for z in zones]
    dests = [p.geometry.centroid for p in candidates]
    matrix = travel_time_matrix(graph, origins, dests)

    problem = FacilityLocationProblem(
        candidate_ids=[str(p.id) for p in candidates],
        demand_ids=[str(z.id) for z in zones],
        demand_weights=[float(z.population or 0.0) for z in zones],
        cost_matrix=matrix,
        p=n_facilities,
        max_cost=(max_minutes * 60.0) if max_minutes else None,
    )

    provenance = ctx.provenance(
        f"optimization.{objective}", ALGORITHM_VERSION,
        extra_parameters={
            "n_facilities": n_facilities,
            "objective": objective,
            "max_minutes": max_minutes,
            "candidates_considered": len(candidates),
            "demand_points": len(zones),
        },
    )

    options = SolveOptions(time_limit_seconds=30.0, seed=42)
    if objective == "max_coverage":
        if max_minutes is None:
            return {"error": "max_coverage requires max_minutes"}
        result = solve_max_coverage(problem, provenance, options)
    else:
        result = solve_facility_location(problem, provenance, options)

    result_id = save_result(engine, result, ctx.scenario_id) if persist else None
    selected = result.records[0].get("selected_sites", []) if result.records else []

    return {
        "result_id": result_id,
        "objective": objective,
        "selected_parcel_ids": selected,
        "metrics": [m.to_dict() for m in result.metrics],
        "assignments": result.records[1:] if len(result.records) > 1 else [],
        "warnings": result.warnings,
        "provenance": result.provenance.to_dict(),
    }
