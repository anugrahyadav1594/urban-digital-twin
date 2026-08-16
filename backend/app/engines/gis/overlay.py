"""Intersection, containment and spatial joins. ARCHITECTURE §12.

All inputs must already be in the analysis CRS. Callers use crs.to_analysis().
"""
from __future__ import annotations

from typing import Any, Callable, Iterable, Sequence

from shapely.strtree import STRtree


def _index(geoms: Sequence[Any]) -> STRtree:
    return STRtree(list(geoms))


def intersects_any(geom: Any, others: Sequence[Any]) -> bool:
    """True if geom intersects at least one of others. R-tree accelerated."""
    if not others:
        return False
    tree = _index(others)
    for idx in tree.query(geom):
        if geom.intersects(others[int(idx)]):
            return True
    return False


def containment(geom: Any, containers: Sequence[Any]) -> list[int]:
    """Indices of containers that fully contain geom."""
    if not containers:
        return []
    tree = _index(containers)
    return [
        int(i) for i in tree.query(geom)
        if containers[int(i)].contains(geom)
    ]


def overlay_area_fraction(geom: Any, others: Sequence[Any]) -> float:
    """Fraction of geom's area covered by the union of others. Range 0..1."""
    if geom.is_empty or geom.area <= 0 or not others:
        return 0.0
    tree = _index(others)
    hits = [others[int(i)] for i in tree.query(geom)]
    if not hits:
        return 0.0
    covered = 0.0
    from shapely.ops import unary_union
    inter = geom.intersection(unary_union(hits))
    covered = inter.area if not inter.is_empty else 0.0
    return max(0.0, min(1.0, covered / geom.area))


def spatial_join(
    left: Sequence[Any],
    right: Sequence[Any],
    predicate: str = "intersects",
) -> dict[int, list[int]]:
    """Map each left index to matching right indices.

    predicate: intersects | within | contains
    """
    if not left or not right:
        return {i: [] for i in range(len(left))}
    tree = _index(right)
    test: Callable[[Any, Any], bool] = {
        "intersects": lambda a, b: a.intersects(b),
        "within": lambda a, b: a.within(b),
        "contains": lambda a, b: a.contains(b),
    }[predicate]

    out: dict[int, list[int]] = {}
    for i, g in enumerate(left):
        out[i] = [int(j) for j in tree.query(g) if test(g, right[int(j)])]
    return out
