"""Geometry normalization between PostGIS storage and engine analysis CRS.

ARCHITECTURE §6.5, §12, §29 (Accuracy).

PostGIS stores EPSG:4326 and uses Multi* geometry columns. The engines need
single-part geometries in a projected CRS. This module is the only place that
conversion happens.
"""
from __future__ import annotations

from typing import Any, Iterable

from pyproj import CRS, Transformer
from shapely.geometry import (
    LineString, MultiLineString, MultiPoint, MultiPolygon, Point, Polygon,
)
from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge, transform as shapely_transform, unary_union

# Navi Mumbai / NAINA pilot zone. Matches etl/coordinate_utils.PROJECTED_CRS.
STORAGE_SRID = 4326
ANALYSIS_SRID = 32643  # UTM Zone 43N

_TRANSFORMERS: dict[tuple[int, int], Transformer] = {}


def _transformer(src: int, dst: int) -> Transformer:
    key = (src, dst)
    if key not in _TRANSFORMERS:
        _TRANSFORMERS[key] = Transformer.from_crs(
            CRS.from_epsg(src), CRS.from_epsg(dst), always_xy=True
        )
    return _TRANSFORMERS[key]


def assert_projected(srid: int) -> None:
    """Refuse metric maths in a geographic CRS (§29)."""
    if CRS.from_epsg(srid).is_geographic:
        raise ValueError(
            f"EPSG:{srid} is geographic; areas and distances would be in "
            "degrees. Use a projected CRS such as 32643."
        )


def to_analysis(geom: BaseGeometry, analysis_srid: int = ANALYSIS_SRID) -> BaseGeometry:
    """EPSG:4326 -> projected analysis CRS."""
    if geom is None:
        return None
    if analysis_srid == STORAGE_SRID:
        return geom
    return shapely_transform(_transformer(STORAGE_SRID, analysis_srid).transform, geom)


def to_storage(geom: BaseGeometry, analysis_srid: int = ANALYSIS_SRID) -> BaseGeometry:
    """Projected analysis CRS -> EPSG:4326 for persistence and GeoJSON."""
    if geom is None:
        return None
    if analysis_srid == STORAGE_SRID:
        return geom
    return shapely_transform(_transformer(analysis_srid, STORAGE_SRID).transform, geom)


def as_linestring(geom: BaseGeometry) -> LineString | None:
    """Coerce a road geometry to a single LineString.

    The roads table is GEOMETRY(MultiLineString, 4326). The graph builder reads
    geom.coords, which raises NotImplementedError on multi-part geometries, so
    every road must be flattened here first. Contiguous parts are merged; if
    the parts are disjoint the longest is used and the caller can split the
    record upstream.
    """
    if geom is None or geom.is_empty:
        return None
    if isinstance(geom, LineString):
        return geom
    if isinstance(geom, MultiLineString):
        merged = linemerge(geom)
        if isinstance(merged, LineString):
            return merged
        parts = sorted(merged.geoms, key=lambda g: g.length, reverse=True)
        return parts[0] if parts else None
    if hasattr(geom, "geoms"):
        lines = [g for g in geom.geoms if isinstance(g, LineString)]
        if lines:
            return max(lines, key=lambda g: g.length)
    return None


def explode_lines(geom: BaseGeometry) -> list[LineString]:
    """All LineString parts of a geometry, preserving disjoint segments.

    Prefer this over as_linestring() when building a road graph: a disjoint
    MultiLineString represents genuinely separate segments and dropping the
    shorter parts would silently delete road network.
    """
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [geom]
    if isinstance(geom, MultiLineString):
        merged = linemerge(geom)
        if isinstance(merged, LineString):
            return [merged]
        return [g for g in merged.geoms if isinstance(g, LineString) and not g.is_empty]
    if hasattr(geom, "geoms"):
        out: list[LineString] = []
        for g in geom.geoms:
            out.extend(explode_lines(g))
        return out
    return []


def as_polygon(geom: BaseGeometry) -> Polygon | None:
    """Coerce to a single Polygon, dissolving MultiPolygon parts."""
    if geom is None or geom.is_empty:
        return None
    if isinstance(geom, Polygon):
        return geom
    if isinstance(geom, MultiPolygon):
        if len(geom.geoms) == 1:
            return geom.geoms[0]
        merged = unary_union(geom)
        if isinstance(merged, Polygon):
            return merged
        return max(geom.geoms, key=lambda g: g.area)
    if hasattr(geom, "buffer"):
        return geom.buffer(0) if geom.geom_type == "Polygon" else None
    return None


def as_point(geom: BaseGeometry) -> Point | None:
    """Coerce any geometry to a representative Point.

    The facilities table is GEOMETRY(Geometry, 4326), so a facility may be a
    point or a building polygon.
    """
    if geom is None or geom.is_empty:
        return None
    if isinstance(geom, Point):
        return geom
    if isinstance(geom, MultiPoint):
        return geom.geoms[0] if len(geom.geoms) else None
    return geom.representative_point()


def repair(geom: BaseGeometry) -> BaseGeometry | None:
    """Fix invalid geometry with a zero buffer. Returns None if unrecoverable."""
    if geom is None or geom.is_empty:
        return None
    if geom.is_valid:
        return geom
    fixed = geom.buffer(0)
    return None if fixed.is_empty else fixed
