"""PostGIS -> engine domain record loaders.

ARCHITECTURE §5.3, §12. This is the boundary where database rows become the
plain dataclasses the engines consume. Engines never see SQLAlchemy, GeoPandas
or the raw schema.

All returned geometries are in the projected ANALYSIS CRS (EPSG:32643), which
is what every engine expects.
"""
from __future__ import annotations

from typing import Any, Iterable, Sequence

from shapely import wkb
from shapely.geometry.base import BaseGeometry
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.engines.contracts import (
    Building, Facility, Parcel, PlanningConstraint, PopulationZone, Road,
)

from .geometry import (
    ANALYSIS_SRID, as_point, as_polygon, explode_lines, repair, to_analysis,
)
from .vocab import (
    constraint_buffer, normalize_facility_type, normalize_land_use,
    normalize_road_class, normalize_severity, severity_weight,
)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _geom(row_geom: Any) -> BaseGeometry | None:
    """Decode a PostGIS geometry (WKB hex from ST_AsBinary/EWKB) to shapely."""
    if row_geom is None:
        return None
    if isinstance(row_geom, BaseGeometry):
        return row_geom
    if isinstance(row_geom, (bytes, bytearray, memoryview)):
        return wkb.loads(bytes(row_geom))
    if isinstance(row_geom, str):
        return wkb.loads(bytes.fromhex(row_geom))
    if hasattr(row_geom, "desc"):          # GeoAlchemy2 WKBElement
        return wkb.loads(bytes(row_geom.data))
    return None


def _f(value: Any, default: float | None = None) -> float | None:
    """Coerce a NUMERIC/Decimal column to float."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _i(value: Any, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _bbox_clause(bbox: Sequence[float] | None, column: str = "geometry") -> str:
    """Optional bbox filter using the GIST index (§29 Performance)."""
    if not bbox:
        return ""
    return (
        f" AND {column} && ST_MakeEnvelope("
        ":minx, :miny, :maxx, :maxy, 4326)"
    )


def _bbox_params(bbox: Sequence[float] | None) -> dict[str, float]:
    if not bbox:
        return {}
    minx, miny, maxx, maxy = bbox
    return {"minx": minx, "miny": miny, "maxx": maxx, "maxy": maxy}


# --------------------------------------------------------------------------
# loaders
# --------------------------------------------------------------------------

def load_roads(
    engine: Engine,
    bbox: Sequence[float] | None = None,
    analysis_srid: int = ANALYSIS_SRID,
    limit: int | None = None,
) -> list[Road]:
    """Load the roads table as engine Road records.

    A MultiLineString row is exploded into one Road per part, keyed
    '{id}#{n}'. Flattening to a single part would silently delete disjoint
    road segments from the network graph.
    """
    sql = (
        "SELECT id, road_class, lanes, width_m, speed_limit, capacity, oneway, "
        "ST_AsBinary(geometry) AS geom FROM roads WHERE geometry IS NOT NULL"
        + _bbox_clause(bbox)
    )
    if limit:
        sql += f" LIMIT {int(limit)}"

    out: list[Road] = []
    with engine.connect() as conn:
        for row in conn.execute(text(sql), _bbox_params(bbox)).mappings():
            geom = _geom(row["geom"])
            if geom is None:
                continue
            parts = explode_lines(to_analysis(geom, analysis_srid))
            for n, part in enumerate(parts):
                rid = str(row["id"]) if len(parts) == 1 else f"{row['id']}#{n}"
                out.append(Road(
                    id=rid,
                    geometry=part,
                    road_class=normalize_road_class(row["road_class"]),
                    width=_f(row["width_m"]),
                    lanes=_i(row["lanes"], 2) or 2,
                    speed=_f(row["speed_limit"], 40.0) or 40.0,
                    capacity=_f(row["capacity"]),
                    oneway=bool(row["oneway"]),
                ))
    return out


def load_buildings(
    engine: Engine,
    bbox: Sequence[float] | None = None,
    analysis_srid: int = ANALYSIS_SRID,
    limit: int | None = None,
) -> list[Building]:
    sql = (
        "SELECT id, height_m, floors, building_type, land_use, confidence, "
        "population_estimate, risk_score, ST_AsBinary(geometry) AS geom "
        "FROM buildings WHERE geometry IS NOT NULL" + _bbox_clause(bbox)
    )
    if limit:
        sql += f" LIMIT {int(limit)}"

    out: list[Building] = []
    with engine.connect() as conn:
        for row in conn.execute(text(sql), _bbox_params(bbox)).mappings():
            geom = _geom(row["geom"])
            poly = as_polygon(repair(to_analysis(geom, analysis_srid))) if geom else None
            if poly is None:
                continue
            out.append(Building(
                id=str(row["id"]),
                geometry=poly,
                height=_f(row["height_m"], 9.0),
                floors=_i(row["floors"], 3),
                building_type=str(row["building_type"] or "residential"),
                land_use=normalize_land_use(row["land_use"]),
                confidence=_f(row["confidence"]),
                population_estimate=_f(row["population_estimate"], 0.0),
                risk_attributes={"risk_score": _f(row["risk_score"], 0.0)},
            ))
    return out


def load_parcels(
    engine: Engine,
    bbox: Sequence[float] | None = None,
    analysis_srid: int = ANALYSIS_SRID,
    limit: int | None = None,
) -> list[Parcel]:
    """Load land_parcels. Area is computed in the projected CRS, not degrees."""
    sql = (
        "SELECT id, land_use, zoning, development_status, slope_deg, "
        "elevation_m, flood_risk, ST_AsBinary(geometry) AS geom "
        "FROM land_parcels WHERE geometry IS NOT NULL" + _bbox_clause(bbox)
    )
    if limit:
        sql += f" LIMIT {int(limit)}"

    out: list[Parcel] = []
    with engine.connect() as conn:
        for row in conn.execute(text(sql), _bbox_params(bbox)).mappings():
            geom = _geom(row["geom"])
            poly = as_polygon(repair(to_analysis(geom, analysis_srid))) if geom else None
            if poly is None:
                continue
            out.append(Parcel(
                id=str(row["id"]),
                geometry=poly,
                area=float(poly.area),                 # m^2 in EPSG:32643
                land_use=normalize_land_use(row["land_use"]),
                zoning=str(row["zoning"] or ""),
                development_status=str(row["development_status"] or "candidate"),
                slope=_f(row["slope_deg"]),
                elevation=_f(row["elevation_m"]),
                flood_risk=_f(row["flood_risk"], 0.0),
            ))
    return out


def load_facilities(
    engine: Engine,
    facility_type: str | None = None,
    bbox: Sequence[float] | None = None,
    analysis_srid: int = ANALYSIS_SRID,
) -> list[Facility]:
    """Load facilities. The column is GEOMETRY(Geometry) so points and
    polygons both occur; everything is reduced to a representative point."""
    sql = (
        "SELECT id, type, name, capacity, service_radius_m, "
        "ST_AsBinary(geometry) AS geom FROM facilities "
        "WHERE geometry IS NOT NULL" + _bbox_clause(bbox)
    )
    params = _bbox_params(bbox)
    if facility_type:
        sql += " AND type = :ftype"
        params["ftype"] = facility_type

    out: list[Facility] = []
    with engine.connect() as conn:
        for row in conn.execute(text(sql), params).mappings():
            geom = _geom(row["geom"])
            pt = as_point(to_analysis(geom, analysis_srid)) if geom else None
            if pt is None:
                continue
            out.append(Facility(
                id=str(row["id"]),
                geometry=pt,
                type=normalize_facility_type(row["type"]),
                capacity=_f(row["capacity"]),
                service_radius=_f(row["service_radius_m"], 2000.0),
            ))
    return out


def load_population_zones(
    engine: Engine,
    bbox: Sequence[float] | None = None,
    analysis_srid: int = ANALYSIS_SRID,
) -> list[PopulationZone]:
    sql = (
        "SELECT id, population, households, density_per_sqkm, "
        "ST_AsBinary(geometry) AS geom FROM population_zones "
        "WHERE geometry IS NOT NULL" + _bbox_clause(bbox)
    )
    out: list[PopulationZone] = []
    with engine.connect() as conn:
        for row in conn.execute(text(sql), _bbox_params(bbox)).mappings():
            geom = _geom(row["geom"])
            poly = as_polygon(repair(to_analysis(geom, analysis_srid))) if geom else None
            if poly is None:
                continue
            out.append(PopulationZone(
                id=str(row["id"]),
                geometry=poly,
                population=_f(row["population"], 0.0) or 0.0,
                density=_f(row["density_per_sqkm"]),
                demographics={"households": _i(row["households"], 0)},
            ))
    return out


def load_constraints(
    engine: Engine,
    bbox: Sequence[float] | None = None,
    analysis_srid: int = ANALYSIS_SRID,
    include_water: bool = True,
) -> list[PlanningConstraint]:
    """Load planning_constraints, optionally adding water bodies as
    constraints with a protective buffer.

    Database severity ('HIGH'/'MEDIUM') is translated to the engine
    'hard'/'soft' vocabulary. Without this every constraint would be treated
    as soft and flood zones would not disqualify a site.
    """
    out: list[PlanningConstraint] = []

    sql = (
        "SELECT id, type, severity, source, ST_AsBinary(geometry) AS geom "
        "FROM planning_constraints WHERE geometry IS NOT NULL"
        + _bbox_clause(bbox)
    )
    with engine.connect() as conn:
        for row in conn.execute(text(sql), _bbox_params(bbox)).mappings():
            geom = _geom(row["geom"])
            poly = as_polygon(repair(to_analysis(geom, analysis_srid))) if geom else None
            if poly is None:
                continue
            raw_sev = row["severity"]
            out.append(PlanningConstraint(
                id=f"constraint-{row['id']}",
                type=str(row["type"]),
                geometry=poly,
                severity=normalize_severity(raw_sev),
                weight=severity_weight(raw_sev),
                buffer=constraint_buffer(row["type"]),
                source=str(row["source"] or "planning_constraints"),
            ))

        if include_water:
            wsql = (
                "SELECT id, type, ST_AsBinary(geometry) AS geom FROM water_bodies "
                "WHERE geometry IS NOT NULL" + _bbox_clause(bbox)
            )
            for row in conn.execute(text(wsql), _bbox_params(bbox)).mappings():
                geom = _geom(row["geom"])
                poly = as_polygon(repair(to_analysis(geom, analysis_srid))) if geom else None
                if poly is None:
                    continue
                out.append(PlanningConstraint(
                    id=f"water-{row['id']}",
                    type="WATER_BODY",
                    geometry=poly,
                    severity="hard",
                    weight=1.0,
                    buffer=constraint_buffer("WATER_BODY"),
                    source="water_bodies",
                ))
    return out


def load_city(
    engine: Engine,
    bbox: Sequence[float] | None = None,
    analysis_srid: int = ANALYSIS_SRID,
) -> dict[str, list[Any]]:
    """Load every collection the scenario resolver expects (§16)."""
    return {
        "roads": load_roads(engine, bbox, analysis_srid),
        "buildings": load_buildings(engine, bbox, analysis_srid),
        "parcels": load_parcels(engine, bbox, analysis_srid),
        "facilities": load_facilities(engine, None, bbox, analysis_srid),
        "population_zones": load_population_zones(engine, bbox, analysis_srid),
        "constraints": load_constraints(engine, bbox, analysis_srid),
        "landuse_zones": [],
        "infrastructure_assets": [],
    }
