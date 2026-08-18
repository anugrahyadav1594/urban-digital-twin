"""Translate ORM rows (EPSG:4326) into engine domain records (projected CRS).

ARCHITECTURE §6.5, §12. This is THE boundary where storage CRS becomes
analysis CRS. Engines do metric maths (area, distance, buffers) and would
silently produce degree-based garbage if handed unprojected geometry, so
every mapper reprojects exactly once, here.

Schema column names differ from the engine field names by design:
    DB height_m        -> Building.height
    DB slope_deg       -> Parcel.slope
    DB speed_limit     -> Road.speed
    DB service_radius_m-> Facility.service_radius
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable, Sequence

from geoalchemy2.shape import to_shape
from shapely.geometry import LineString, MultiLineString
from shapely.wkt import loads as wkt_loads
from shapely.wkb import loads as wkb_loads


def safe_to_shape(geom: Any) -> Any:
    if geom is None:
        return None
    if isinstance(geom, (str, bytes)):
        if isinstance(geom, str):
            if "SRID=" in geom or any(geom.startswith(k) for k in ("POINT", "LINESTRING", "POLYGON", "MULTI")):
                s = geom.split(";", 1)[-1]
                return wkt_loads(s)
            try:
                return wkb_loads(bytes.fromhex(geom))
            except Exception:
                return wkt_loads(geom)
        return wkb_loads(geom)
    if hasattr(geom, "data"):
        data = geom.data
        if isinstance(data, str):
            if "SRID=" in data or any(data.startswith(k) for k in ("POINT", "LINESTRING", "POLYGON", "MULTI")):
                return wkt_loads(data.split(";", 1)[-1])
            try:
                return wkb_loads(bytes.fromhex(data))
            except Exception:
                return wkt_loads(data)
    return to_shape(geom)


from ..core.config import get_settings
from ..engines.contracts import (
    Building, Facility, Parcel, PlanningConstraint, PopulationZone, Road,
)
from ..engines.crs import to_analysis

# Severity strings used by the NAGAR-X schema ('HIGH'/'MEDIUM'/'LOW')
# mapped onto the engine's hard/soft model (§9.6).
_SEVERITY_MAP = {
    "HIGH": "hard", "CRITICAL": "hard", "SEVERE": "hard",
    "MEDIUM": "soft", "LOW": "soft", "MODERATE": "soft",
}
_SEVERITY_WEIGHT = {"MEDIUM": 0.6, "MODERATE": 0.6, "LOW": 0.3}


def _f(v: Any) -> float | None:
    """Numeric(x,y) arrives as Decimal; engines expect float."""
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def _geom(row: Any, srid: int) -> Any:
    """WKBElement -> shapely, reprojected into the analysis CRS."""
    return to_analysis(safe_to_shape(row.geometry), srid)


def _first_line(geom: Any) -> Any:
    """Roads are stored as MultiLineString; the graph builder wants LineStrings.

    Returns the geometry unchanged when it is already a LineString.
    """
    if isinstance(geom, MultiLineString):
        parts = list(geom.geoms)
        return parts[0] if len(parts) == 1 else geom
    return geom


def _srid() -> int:
    return get_settings().analysis_srid


# ---------------------------------------------------------------------------
# Row -> domain record
# ---------------------------------------------------------------------------


def to_parcel(row: Any, srid: int | None = None) -> Parcel:
    srid = srid or _srid()
    geom = _geom(row, srid)
    return Parcel(
        id=str(row.id),
        geometry=geom,
        area=float(geom.area),                 # m^2 in the projected CRS
        land_use=row.land_use,
        zoning=row.zoning,
        development_status=row.development_status or "candidate",
        slope=_f(row.slope_deg),
        elevation=_f(row.elevation_m),
        flood_risk=_f(row.flood_risk),
        attributes={"source": row.source},
    )


def to_building(row: Any, srid: int | None = None) -> Building:
    srid = srid or _srid()
    return Building(
        id=str(row.id),
        geometry=_geom(row, srid),
        height=_f(row.height_m),
        floors=row.floors,
        building_type=row.building_type,
        land_use=row.land_use,
        confidence=_f(row.confidence),
        population_estimate=_f(row.population_estimate),
        risk_attributes={"risk_score": _f(row.risk_score)},
    )


def to_road(row: Any, srid: int | None = None) -> Road:
    srid = srid or _srid()
    return Road(
        id=str(row.id),
        geometry=_first_line(_geom(row, srid)),
        road_class=row.road_class or "residential",
        width=_f(row.width_m),
        lanes=row.lanes or 2,
        speed=_f(row.speed_limit) or 40.0,
        capacity=_f(row.capacity),
        oneway=bool(row.oneway),
    )


def to_facility(row: Any, srid: int | None = None) -> Facility:
    """Facilities may be points or polygons; engines expect a point."""
    srid = srid or _srid()
    geom = _geom(row, srid)
    if geom.geom_type != "Point":
        geom = geom.centroid
    return Facility(
        id=str(row.id),
        geometry=geom,
        type=row.type,
        capacity=_f(row.capacity),
        service_radius=_f(row.service_radius_m),
    )


def to_population_zone(row: Any, srid: int | None = None) -> PopulationZone:
    srid = srid or _srid()
    return PopulationZone(
        id=str(row.id),
        geometry=_geom(row, srid),
        population=float(row.population or 0.0),
        density=_f(row.density_per_sqkm),
        demographics={"households": row.households},
    )


def to_constraint(row: Any, srid: int | None = None) -> PlanningConstraint:
    srid = srid or _srid()
    sev_raw = (row.severity or "HIGH").upper()
    return PlanningConstraint(
        id=str(row.id),
        type=row.type,
        geometry=_geom(row, srid),
        severity=_SEVERITY_MAP.get(sev_raw, "hard"),
        weight=_SEVERITY_WEIGHT.get(sev_raw, 1.0),
        buffer=0.0,
        source=row.source,
    )


def map_all(rows: Iterable[Any], fn, srid: int | None = None) -> list[Any]:
    srid = srid or _srid()
    return [fn(r, srid) for r in rows]
