"""Shortest paths and travel time. ARCHITECTURE §13."""
from __future__ import annotations

from typing import Any, Sequence

import networkx as nx


def nearest_node(G: nx.DiGraph, point: Any) -> tuple[float, float] | None:
    """Closest graph node to a shapely point (linear scan; fine at pilot scale)."""
    if G.number_of_nodes() == 0:
        return None
    px, py = point.x, point.y
    best, best_d = None, float("inf")
    for n in G.nodes:
        d = (n[0] - px) ** 2 + (n[1] - py) ** 2
        if d < best_d:
            best, best_d = n, d
    return best


def shortest_path(
    G: nx.DiGraph, source: Any, target: Any, weight: str = "time"
) -> tuple[list[tuple[float, float]], float] | None:
    """(path nodes, total weight). None when unreachable."""
    try:
        path = nx.shortest_path(G, source, target, weight=weight)
        cost = nx.shortest_path_length(G, source, target, weight=weight)
        return path, float(cost)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def travel_time(
    G: nx.DiGraph, origin: Any, destination: Any
) -> float | None:
    """Travel time in seconds between two shapely points. None if unreachable."""
    s, t = nearest_node(G, origin), nearest_node(G, destination)
    if s is None or t is None:
        return None
    res = shortest_path(G, s, t, weight="time")
    return None if res is None else res[1]


def travel_time_matrix(
    G: nx.DiGraph, origins: Sequence[Any], destinations: Sequence[Any]
) -> list[list[float | None]]:
    """Seconds from each origin to each destination, via multi-source Dijkstra."""
    dest_nodes = [nearest_node(G, d) for d in destinations]
    matrix: list[list[float | None]] = []
    for o in origins:
        s = nearest_node(G, o)
        if s is None:
            matrix.append([None] * len(destinations))
            continue
        lengths = nx.single_source_dijkstra_path_length(G, s, weight="time")
        matrix.append([
            None if dn is None else lengths.get(dn) for dn in dest_nodes
        ])
    return matrix
