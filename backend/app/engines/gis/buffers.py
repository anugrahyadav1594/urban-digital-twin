"""Buffers, setbacks and exclusion zones. ARCHITECTURE §12."""
from __future__ import annotations

from typing import Any, Iterable, Sequence

from shapely.ops import unary_union


def buffer_geometry(geom: Any, distance: float, resolution: int = 16) -> Any:
    """Buffer in analysis-CRS units (metres). Negative shrinks (setbacks)."""
    return geom.buffer(distance, resolution=resolution)


def buffered_union(geoms: Sequence[Any], distance: float) -> Any:
    """Dissolved buffer around many geometries — service rings, corridors."""
    if not geoms:
        from shapely.geometry import GeometryCollection
        return GeometryCollection()
    return unary_union([g.buffer(distance) for g in geoms])


def exclusion_mask(
    constraint_geoms: Sequence[Any],
    buffers: Sequence[float] | None = None,
) -> Any:
    """Union of constraint areas, each with its own outward buffer.

    Anything intersecting the mask is disqualified by hard-constraint filtering.
    """
    if not constraint_geoms:
        from shapely.geometry import GeometryCollection
        return GeometryCollection()
    if buffers is None:
        buffers = [0.0] * len(constraint_geoms)
    if len(buffers) != len(constraint_geoms):
        raise ValueError("buffers length must match constraint_geoms length")
    parts = [
        g.buffer(b) if b else g
        for g, b in zip(constraint_geoms, buffers)
    ]
    return unary_union(parts)
