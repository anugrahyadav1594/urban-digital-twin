"""CRS policy. ARCHITECTURE §6.5, §29 (Accuracy).

Storage CRS is EPSG:4326. All area/distance/buffer maths must happen in a
local projected CRS. Engines never guess: the analysis SRID is passed in and
recorded on every result.
"""
from __future__ import annotations

from typing import Any

from pyproj import CRS, Transformer
from shapely.geometry import shape as shapely_shape
from shapely.ops import transform as shapely_transform

STORAGE_SRID = 4326
DEFAULT_ANALYSIS_SRID = 32644  # UTM 44N — eastern Uttar Pradesh

_TRANSFORMER_CACHE: dict[tuple[int, int], Transformer] = {}


def get_transformer(src_srid: int, dst_srid: int) -> Transformer:
    key = (src_srid, dst_srid)
    if key not in _TRANSFORMER_CACHE:
        _TRANSFORMER_CACHE[key] = Transformer.from_crs(
            CRS.from_epsg(src_srid), CRS.from_epsg(dst_srid), always_xy=True
        )
    return _TRANSFORMER_CACHE[key]


def reproject(geom: Any, src_srid: int, dst_srid: int) -> Any:
    """Reproject a shapely geometry between two EPSG codes."""
    if src_srid == dst_srid:
        return geom
    tf = get_transformer(src_srid, dst_srid)
    return shapely_transform(tf.transform, geom)


def to_analysis(geom: Any, analysis_srid: int = DEFAULT_ANALYSIS_SRID) -> Any:
    """EPSG:4326 -> projected analysis CRS."""
    return reproject(geom, STORAGE_SRID, analysis_srid)


def to_storage(geom: Any, analysis_srid: int = DEFAULT_ANALYSIS_SRID) -> Any:
    """Projected analysis CRS -> EPSG:4326."""
    return reproject(geom, analysis_srid, STORAGE_SRID)


def assert_projected(analysis_srid: int) -> None:
    """Guard: refuse to do metric maths in a geographic CRS (§29 Accuracy)."""
    crs = CRS.from_epsg(analysis_srid)
    if crs.is_geographic:
        raise ValueError(
            f"EPSG:{analysis_srid} is geographic; area/distance results would be "
            "in degrees. Supply a projected CRS (e.g. 32644)."
        )


def utm_srid_for(lon: float, lat: float) -> int:
    """Pick the UTM zone SRID for a lon/lat, for pilot zones outside UP."""
    zone = int((lon + 180.0) / 6.0) + 1
    return (32600 if lat >= 0 else 32700) + zone


def geojson_to_geometry(obj: dict) -> Any:
    return shapely_shape(obj)
