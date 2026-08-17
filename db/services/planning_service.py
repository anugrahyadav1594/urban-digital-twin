"""Site suitability service: PostGIS -> planning engine -> PostGIS.

ARCHITECTURE §14, §22, §23.
"""
from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy.engine import Engine

from app.engines.network.graph_builder import build_graph
from app.engines.planning import DEFAULT_PROFILES, SiteRequirements, site_suitability

from db.adapters.loaders import (
    load_constraints, load_facilities, load_parcels, load_population_zones,
    load_roads,
)
from db.adapters.writers import result_to_geojson, save_result

from .context import AnalysisContext

ALGORITHM = "planning.site_suitability"
ALGORITHM_VERSION = "0.1.0"


def find_best_sites(
    engine: Engine,
    facility_type: str = "hospital",
    ctx: AnalysisContext | None = None,
    top_n: int = 5,
    required_area: float = 5000.0,
    max_slope: float | None = 15.0,
    max_flood_risk: float | None = 0.30,
    min_distance_same_type: float | None = 1000.0,
    service_radius: float = 2000.0,
    use_network: bool = True,
    persist: bool = True,
) -> dict[str, Any]:
    """Rank candidate parcels for a new facility.

    Returns the engine result, GeoJSON for CesiumJS, and the stored result id.
    """
    ctx = ctx or AnalysisContext()

    parcels = load_parcels(engine, ctx.bbox, ctx.analysis_srid)
    if not parcels:
        return {
            "error": "no land parcels found",
            "hint": "run the ETL pipeline (etl/run_full_etl.py) first",
            "candidates": [],
        }

    constraints = load_constraints(engine, ctx.bbox, ctx.analysis_srid)
    zones = load_population_zones(engine, ctx.bbox, ctx.analysis_srid)
    facilities = load_facilities(engine, None, ctx.bbox, ctx.analysis_srid)

    graph = None
    if use_network:
        roads = load_roads(engine, ctx.bbox, ctx.analysis_srid)
        if roads:
            graph = build_graph(roads, mode="car")

    profile = DEFAULT_PROFILES.get(facility_type, DEFAULT_PROFILES["hospital"])

    requirements = SiteRequirements(
        facility_type=facility_type,
        required_area=required_area,
        max_slope=max_slope,
        max_flood_risk=max_flood_risk,
        min_distance_same_type=min_distance_same_type,
        allowed_status=("candidate", "vacant", "under_development"),
    )

    provenance = ctx.provenance(
        ALGORITHM, ALGORITHM_VERSION,
        extra_parameters={
            "facility_type": facility_type,
            "required_area": required_area,
            "max_slope": max_slope,
            "max_flood_risk": max_flood_risk,
            "min_distance_same_type": min_distance_same_type,
            "service_radius": service_radius,
            "network_used": graph is not None,
        },
        scoring_profile_version=profile.version,
    )

    result = site_suitability(
        parcels=parcels,
        requirements=requirements,
        provenance=provenance,
        constraints=constraints,
        population_zones=zones,
        existing_facilities=facilities,
        graph=graph,
        profile=profile,
        service_radius=service_radius,
        top_n=top_n,
    )

    result_id = save_result(engine, result, ctx.scenario_id) if persist else None

    geoms = {str(p.id): p.geometry for p in parcels}
    geojson = result_to_geojson(result, geoms, ctx.analysis_srid)

    return {
        "result_id": result_id,
        "facility_type": facility_type,
        "candidates": result.records,
        "metrics": [m.to_dict() for m in result.metrics],
        "warnings": result.warnings,
        "provenance": result.provenance.to_dict(),
        "geojson": geojson,
    }
