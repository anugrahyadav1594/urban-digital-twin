"""Shortest paths and travel time. ARCHITECTURE §13."""
from __future__ import annotations

from typing import Any, Sequence

import networkx as nx

try:                                    # optional; falls back to a linear scan
    from scipy.spatial import cKDTree
except ImportError:                     # pragma: no cover
    cKDTree = None

# Per-graph spatial index for nearest_node. Keyed by id(G) and invalidated by
# node count, so a rebuilt graph never reuses a stale tree.
_INDEX_CACHE: dict[int, tuple[int, Any, list]] = {}


def _index(G: nx.DiGraph):
    key = id(G)
    hit = _INDEX_CACHE.get(key)
    if hit is not None and hit[0] == G.number_of_nodes():
        return hit[1], hit[2]
    nodes = list(G.nodes)
    tree = cKDTree(nodes) if (cKDTree is not None and nodes) else None
    _INDEX_CACHE[key] = (G.number_of_nodes(), tree, nodes)
    return tree, nodes


def nearest_node(G: nx.DiGraph, point: Any) -> tuple[float, float] | None:
    """Closest graph node to a shapely point.

    A linear scan is O(nodes) per call, which at city scale (12k nodes,
    thousands of lookups) dominated runtime. Uses a cached KD-tree when SciPy
    is available and falls back to the original scan otherwise.
    """
    if G.number_of_nodes() == 0:
        return None
    px, py = point.x, point.y
    tree, nodes = _index(G)
    if tree is not None:
        return tuple(nodes[int(tree.query((px, py))[1])])
    best, best_d = None, float("inf")
    for n in nodes:
        d = (n[0] - px) ** 2 + (n[1] - py) ** 2
        if d < best_d:
            best, best_d = n, d
    return best


# Largest strongly connected component, cached per graph. Routing between two
# nodes of this set is always possible; snapping to it is what stops a station
# that sits on a driveway or an unnoded service road from reporting
# "unreachable" when the city network is perfectly fine.
# Keyed by id(G) but validated on (nodes, edges): degrade_graph() returns a
# copy with the same node count and fewer edges, and CPython recycles ids, so
# node count alone would hand back the undegraded core.
_CORE_CACHE: dict[int, tuple[tuple[int, int], frozenset]] = {}


def routable_core(G: nx.DiGraph) -> frozenset:
    """Nodes of the largest strongly connected component of G."""
    key = id(G)
    sig = (G.number_of_nodes(), G.number_of_edges())
    hit = _CORE_CACHE.get(key)
    if hit is not None and hit[0] == sig:
        return hit[1]
    if G.number_of_nodes() == 0:
        core: frozenset = frozenset()
    else:
        core = frozenset(max(nx.strongly_connected_components(G), key=len))
    _CORE_CACHE[key] = (sig, core)
    return core


def nearest_node_in(
    G: nx.DiGraph, point: Any, allowed: frozenset | set | None = None
) -> tuple[tuple[float, float] | None, float]:
    """Nearest node restricted to `allowed`, plus the snap distance in metres.

    Real road data always contains fragments that touch nothing: service
    spurs, driveways, segments whose endpoints missed each other after
    reprojection. Snapping blindly to the closest node drops a responder onto
    one of those islands and every route from it fails. Restricting the snap
    to a mutually reachable set trades a few metres of positional accuracy for
    an answer that exists.
    """
    if G.number_of_nodes() == 0:
        return None, 0.0
    px, py = point.x, point.y
    if not allowed:
        n = nearest_node(G, point)
        if n is None:
            return None, 0.0
        return n, ((n[0] - px) ** 2 + (n[1] - py) ** 2) ** 0.5
    best, best_d = None, float("inf")
    for n in allowed:
        d = (n[0] - px) ** 2 + (n[1] - py) ** 2
        if d < best_d:
            best, best_d = n, d
    if best is None:
        return None, 0.0
    return best, best_d ** 0.5


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
    G: nx.DiGraph,
    origins: Sequence[Any],
    destinations: Sequence[Any],
    cutoff_seconds: float | None = None,
) -> list[list[float | None]]:
    """Seconds from each origin to each destination.

    One Dijkstra per origin. `cutoff_seconds` bounds each search: anything
    beyond the cutoff is None, which is what a caller filtering by a travel
    time threshold wants anyway. Without it, every origin explores the whole
    graph - at city scale that was ~99% wasted work.
    """
    dest_nodes = [nearest_node(G, d) for d in destinations]
    # Distinct sources only: many origins can snap to the same graph node.
    cache: dict[Any, dict] = {}
    matrix: list[list[float | None]] = []
    for o in origins:
        s = nearest_node(G, o)
        if s is None:
            matrix.append([None] * len(destinations))
            continue
        lengths = cache.get(s)
        if lengths is None:
            lengths = nx.single_source_dijkstra_path_length(
                G, s, cutoff=cutoff_seconds, weight="time")
            cache[s] = lengths
        matrix.append([
            None if dn is None else lengths.get(dn) for dn in dest_nodes
        ])
    return matrix


