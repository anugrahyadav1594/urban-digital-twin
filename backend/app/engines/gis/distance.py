"""Euclidean distance and nearest-facility queries. ARCHITECTURE §12.

Straight-line only. Network distance/time belongs to the network engine (§13).
"""
from __future__ import annotations

from typing import Any, Sequence

from shapely.strtree import STRtree


def min_distance_to_any(geom: Any, others: Sequence[Any]) -> float | None:
    """Shortest distance (m) from geom to any of others; None if empty."""
    if not others:
        return None
    tree = STRtree(list(others))
    idx = tree.nearest(geom)
    if idx is None:
        return None
    return float(geom.distance(others[int(idx)]))


def nearest_facility(geom: Any, facilities: Sequence[Any]) -> tuple[int, float] | None:
    """(index, distance_m) of the closest facility. Facilities are records
    exposing a .geometry attribute."""
    if not facilities:
        return None
    geoms = [f.geometry for f in facilities]
    tree = STRtree(geoms)
    idx = tree.nearest(geom)
    if idx is None:
        return None
    i = int(idx)
    return i, float(geom.distance(geoms[i]))


def k_nearest_facilities(
    geom: Any,
    facilities: Sequence[Any],
    k: int = 3,
    facility_type: str | None = None,
    max_distance: float | None = None,
) -> list[tuple[int, float]]:
    """Up to k nearest facilities as (index, distance_m), sorted ascending."""
    cand = [
        (i, f) for i, f in enumerate(facilities)
        if facility_type is None or getattr(f, "type", None) == facility_type
    ]
    if not cand:
        return []
    scored = [(i, float(geom.distance(f.geometry))) for i, f in cand]
    if max_distance is not None:
        scored = [s for s in scored if s[1] <= max_distance]
    scored.sort(key=lambda t: (t[1], t[0]))
    return scored[:k]


def distance_matrix(
    origins: Sequence[Any], destinations: Sequence[Any]
) -> list[list[float]]:
    """Dense O(n*m) Euclidean matrix in metres."""
    return [[float(o.distance(d)) for d in destinations] for o in origins]
