"""Accessibility and emergency-response services.

ARCHITECTURE §13, §17, §22.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.engine import Engine

from app.engines.network import (
    accessibility_metrics, build_graph, compare_accessibility,
    emergency_response, population_to_facility,
)
from app.engines.network.service_area import service_area_polygon
from app.engines.simulation import demand_vs_capacity, resilience_analysis

from db.adapters.geometry import to_storage
from db.adapters.loaders import (
    load_facilities, load_population_zones, load_roads,
)
from db.adapters.writers import save_result

from .context import AnalysisContext

ALGORITHM_VERSION = "0.1.0"


def _graph(engine: Engine, ctx: AnalysisContext, mode: str = "car"):
    roads = load_roads(engine, ctx.bbox, ctx.analysis_srid)
    if not roads:
        return None, 0
    return build_graph(roads, mode=mode), len(roads)


def analyze_accessibility(
    engine: Engine,
    facility_type: str = "hospital",
    threshold_minutes: float = 15.0,
    ctx: AnalysisContext | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Population-weighted accessibility to the nearest facility of a type."""
    ctx = ctx or AnalysisContext()
    graph, n_roads = _graph(engine, ctx)
    if graph is None:
        return {"error": "no roads in database; run the ETL pipeline first"}

    facilities = load_facilities(engine, facility_type, ctx.bbox, ctx.analysis_srid)
    zones = load_population_zones(engine, ctx.bbox, ctx.analysis_srid)

    provenance = ctx.provenance(
        "network.accessibility", ALGORITHM_VERSION,
        extra_parameters={
            "facility_type": facility_type,
            "threshold_seconds": threshold_minutes * 60.0,
            "road_segments": n_roads,
            "mode_profile": "car",
        },
    )
    result = accessibility_metrics(
        graph, facilities, zones, provenance,
        threshold_seconds=threshold_minutes * 60.0,
    )
    result_id = save_result(engine, result, ctx.scenario_id) if persist else None
    return {
        "result_id": result_id,
        "metrics": [m.to_dict() for m in result.metrics],
        "zones": result.records,
        "warnings": result.warnings,
        "provenance": result.provenance.to_dict(),
    }


def analyze_emergency_response(
    engine: Engine,
    station_type: str = "fire_station",
    response_minutes: float = 8.0,
    ctx: AnalysisContext | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Coverage against an emergency response-time commitment."""
    ctx = ctx or AnalysisContext()
    graph, n_roads = _graph(engine, ctx, mode="emergency")
    if graph is None:
        return {"error": "no roads in database; run the ETL pipeline first"}

    stations = load_facilities(engine, station_type, ctx.bbox, ctx.analysis_srid)
    zones = load_population_zones(engine, ctx.bbox, ctx.analysis_srid)

    provenance = ctx.provenance(
        "network.emergency_response", ALGORITHM_VERSION,
        extra_parameters={
            "station_type": station_type,
            "response_threshold_seconds": response_minutes * 60.0,
            "road_segments": n_roads,
            "mode_profile": "emergency",
        },
    )
    result = emergency_response(
        graph, stations, zones, provenance,
        response_threshold_seconds=response_minutes * 60.0,
    )
    result_id = save_result(engine, result, ctx.scenario_id) if persist else None
    return {
        "result_id": result_id,
        "metrics": [m.to_dict() for m in result.metrics],
        "zones": result.records,
        "warnings": result.warnings,
    }


def compute_service_area(
    engine: Engine,
    lat: float,
    lon: float,
    minutes: float = 10.0,
    ctx: AnalysisContext | None = None,
) -> dict[str, Any]:
    """Isochrone polygon around a point, returned as EPSG:4326 GeoJSON."""
    from shapely.geometry import Point

    from db.adapters.geometry import to_analysis

    ctx = ctx or AnalysisContext()
    graph, _ = _graph(engine, ctx)
    if graph is None:
        return {"error": "no roads in database; run the ETL pipeline first"}

    origin = to_analysis(Point(lon, lat), ctx.analysis_srid)
    poly = service_area_polygon(graph, origin, minutes * 60.0)
    zones = load_population_zones(engine, ctx.bbox, ctx.analysis_srid)

    from app.engines.gis.aggregation import coverage_ratio
    served, total, ratio = coverage_ratio(poly, zones)

    return {
        "origin": {"lat": lat, "lon": lon},
        "cutoff_minutes": minutes,
        "population_served": round(served, 1),
        "population_total": round(total, 1),
        "coverage_ratio": round(ratio, 4),
        "geojson": {
            "type": "Feature",
            "properties": {"cutoff_minutes": minutes,
                           "population_served": round(served, 1)},
            "geometry": to_storage(poly, ctx.analysis_srid).__geo_interface__,
        },
    }


def analyze_capacity(
    engine: Engine,
    facility_type: str = "hospital",
    ctx: AnalysisContext | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Installed capacity vs demand implied by planning standards."""
    ctx = ctx or AnalysisContext()
    zones = load_population_zones(engine, ctx.bbox, ctx.analysis_srid)
    facilities = load_facilities(engine, None, ctx.bbox, ctx.analysis_srid)

    provenance = ctx.provenance(
        "simulation.infrastructure_demand", ALGORITHM_VERSION,
        extra_parameters={"facility_type": facility_type},
    )
    result = demand_vs_capacity(zones, facilities, facility_type, provenance)
    result_id = save_result(engine, result, ctx.scenario_id) if persist else None
    return {
        "result_id": result_id,
        "metrics": [m.to_dict() for m in result.metrics],
        "zones": result.records,
        "warnings": result.warnings,
    }


def analyze_resilience(
    engine: Engine,
    ctx: AnalysisContext | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Road-network redundancy and single points of failure."""
    ctx = ctx or AnalysisContext()
    graph, n_roads = _graph(engine, ctx)
    if graph is None:
        return {"error": "no roads in database; run the ETL pipeline first"}

    facilities = load_facilities(engine, None, ctx.bbox, ctx.analysis_srid)
    provenance = ctx.provenance(
        "simulation.resilience", ALGORITHM_VERSION,
        extra_parameters={"road_segments": n_roads},
    )
    result = resilience_analysis(graph, provenance, facilities=facilities)
    result_id = save_result(engine, result, ctx.scenario_id) if persist else None
    return {
        "result_id": result_id,
        "metrics": [m.to_dict() for m in result.metrics],
        "warnings": result.warnings,
    }
