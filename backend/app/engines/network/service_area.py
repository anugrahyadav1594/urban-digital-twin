"""Service areas and isochrones. ARCHITECTURE §13."""
from __future__ import annotations

from typing import Any, Sequence

import networkx as nx
from shapely.geometry import MultiPoint, Point
from shapely.ops import unary_union

from .routing import nearest_node


def service_area_nodes(
    G: nx.DiGraph, origin: Any, cutoff_seconds: float
) -> list[tuple[float, float]]:
    """Nodes reachable from origin within the time cutoff."""
    s = nearest_node(G, origin)
    if s is None:
        return []
    lengths = nx.single_source_dijkstra_path_length(
        G, s, cutoff=cutoff_seconds, weight="time"
    )
    return list(lengths.keys())


def service_area_polygon(
    G: nx.DiGraph,
    origin: Any,
    cutoff_seconds: float,
    buffer_m: float = 50.0,
) -> Any:
    """Reachable extent as a polygon.

    Buffered convex hull of reachable nodes. Deliberately approximate — the
    node set is authoritative, the polygon is for display and coverage maths.
    """
    nodes = service_area_nodes(G, origin, cutoff_seconds)
    if not nodes:
        return Point(origin.x, origin.y).buffer(buffer_m)
    if len(nodes) < 3:
        return unary_union([Point(*n).buffer(buffer_m) for n in nodes])
    return MultiPoint([Point(*n) for n in nodes]).convex_hull.buffer(buffer_m)


def isochrone(
    G: nx.DiGraph,
    origin: Any,
    cutoffs_seconds: Sequence[float],
    buffer_m: float = 50.0,
) -> dict[float, Any]:
    """Nested service-area bands, e.g. 5/10/15 minutes."""
    return {
        float(c): service_area_polygon(G, origin, c, buffer_m)
        for c in sorted(cutoffs_seconds)
    }
