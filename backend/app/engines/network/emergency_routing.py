"""Emergency vehicle routing. ARCHITECTURE §13.

Finds which station responds to an incident and by what road path, under
optionally degraded network conditions (blocked or slowed roads).

Two things separate this from a generic shortest path:

  * The dispatch decision is "which unit arrives first", not "which station is
    nearest as the crow flies". With one-way streets and blockages the nearest
    station is frequently not the fastest, so every station is evaluated.
  * Blockages must change the answer. A route that ignores a closed road is
    worse than useless in an emergency, so impassable edges are removed from
    the graph rather than merely penalised.
"""
from __future__ import annotations

from typing import Any, Iterable, Sequence

import networkx as nx

from ..contracts import EngineResult, Provenance
from .routing import nearest_node, shortest_path

ALGORITHM = "network.emergency_routing"
ALGORITHM_VERSION = "0.1.0"

# Seconds lost before a vehicle is moving. Response time that ignores this
# reads far better than reality; every fire service plans around it.
DEFAULT_TURNOUT_SECONDS = 60.0


def degrade_graph(
    G: nx.DiGraph,
    blocked_road_ids: Iterable[str] = (),
    slowed_road_ids: Iterable[str] = (),
    slow_factor: float = 3.0,
    blocked_geoms: Sequence[Any] = (),
) -> tuple[nx.DiGraph, dict[str, int]]:
    """Copy of G with hazard effects applied. Returns (graph, edge counts).

    `blocked_geoms` removes any edge whose endpoints fall inside a hazard
    polygon — this is how a flood or fire footprint closes roads that were
    never individually identified.
    """
    H = G.copy()
    blocked = {str(i) for i in blocked_road_ids}
    slowed = {str(i) for i in slowed_road_ids}
    stats = {"blocked": 0, "slowed": 0, "blocked_by_geometry": 0}

    drop: list[tuple] = []
    for u, v, data in H.edges(data=True):
        # node_roads() planarizes the network and renames the pieces of a
        # split road to "<parent_id>#<n>". Matching the raw edge id would
        # silently miss every road that crosses another one - which is most
        # of them - so the parent id is what must be compared.
        raw = str(data.get("road_id", ""))
        rid = raw.split("#", 1)[0]
        if rid in blocked or raw in blocked:
            drop.append((u, v))
            stats["blocked"] += 1
        elif rid in slowed or raw in slowed:
            data["time"] = float(data.get("time", 0.0)) * max(slow_factor, 1.0)
            stats["slowed"] += 1

    if blocked_geoms:
        from shapely.geometry import Point
        from shapely.ops import unary_union
        hazard = unary_union(list(blocked_geoms))
        for u, v in list(H.edges()):
            if (u, v) in drop:
                continue
            # Midpoint test: an edge crossing the hazard is impassable even
            # when both endpoints sit outside it.
            mid = Point((u[0] + v[0]) / 2.0, (u[1] + v[1]) / 2.0)
            if hazard.contains(mid) or hazard.contains(Point(u)) or hazard.contains(Point(v)):
                drop.append((u, v))
                stats["blocked_by_geometry"] += 1

    H.remove_edges_from(drop)
    return H, stats


def _path_geometry(path: Sequence[tuple[float, float]]) -> list[list[float]]:
    return [[float(x), float(y)] for x, y in path]


def route_to_incident(
    G: nx.DiGraph,
    incident_point: Any,
    stations: Sequence[Any],
    provenance: Provenance,
    top_n: int = 3,
    turnout_seconds: float = DEFAULT_TURNOUT_SECONDS,
    response_target_seconds: float = 480.0,
) -> EngineResult:
    """Rank stations by time to reach the incident and return their routes."""
    res = EngineResult(result_type="emergency_route", provenance=provenance)

    if G is None or G.number_of_nodes() == 0:
        res.warnings.append("no road network available; cannot route")
        res.records = []
        return res
    if not stations:
        res.warnings.append("no responding stations supplied")
        res.records = []
        return res

    target = nearest_node(G, incident_point)
    if target is None:
        res.warnings.append("incident could not be snapped to the road network")
        res.records = []
        return res

    # When the hazard closes the roads at the incident itself, the nearest node
    # is isolated and every route reports "unreachable" — which is misleading.
    # Real dispatch stages at the edge of the hazard and crews approach on
    # foot, so fall back to the closest node that still has connectivity and
    # report the staging distance honestly.
    staged_from_m = 0.0
    if G.in_degree(target) == 0 and G.out_degree(target) == 0:
        px, py = incident_point.x, incident_point.y
        best, best_d = None, float("inf")
        for n in G.nodes:
            if G.in_degree(n) == 0 and G.out_degree(n) == 0:
                continue
            d = (n[0] - px) ** 2 + (n[1] - py) ** 2
            if d < best_d:
                best, best_d = n, d
        if best is None:
            res.warnings.append(
                "the entire road network is severed; no unit can be staged")
            res.records = []
            return res
        target = best
        staged_from_m = round(best_d ** 0.5, 1)
        res.add("staging_distance_m", staged_from_m, "m")
        res.warnings.append(
            f"roads at the incident are impassable; units stage {staged_from_m:.0f} m "
            "away and approach on foot")

    rows: list[dict[str, Any]] = []
    unreachable = 0
    for st in stations:
        geom = getattr(st, "geometry", None)
        if geom is None:
            continue
        src = nearest_node(G, geom.centroid if hasattr(geom, "centroid") else geom)
        if src is None:
            continue
        found = shortest_path(G, src, target, weight="time")
        if found is None:
            unreachable += 1
            continue
        path, drive = found
        distance = 0.0
        for a, b in zip(path[:-1], path[1:]):
            ed = G.get_edge_data(a, b) or {}
            distance += float(ed.get("length", 0.0))
        total = float(drive) + float(turnout_seconds)
        rows.append({
            "staging_distance_m": staged_from_m,
            "station_id": str(getattr(st, "id", "")),
            "station_name": getattr(st, "name", None) or f"Station {getattr(st, 'id', '')}",
            "station_type": getattr(st, "type", None),
            "drive_time_s": round(float(drive), 1),
            "turnout_s": round(float(turnout_seconds), 1),
            "response_time_s": round(total, 1),
            "response_time_min": round(total / 60.0, 2),
            "distance_m": round(distance, 1),
            "within_target": total <= response_target_seconds,
            "path": _path_geometry(path),
        })

    rows.sort(key=lambda r: (r["response_time_s"], r["station_id"]))
    for i, r in enumerate(rows, start=1):
        r["rank"] = i
        r["is_primary"] = i == 1

    res.records = rows[:max(top_n, 1)]
    res.add("stations_evaluated", len(stations), "count")
    res.add("stations_reachable", len(rows), "count")
    if unreachable:
        res.add("stations_unreachable", unreachable, "count")
        res.warnings.append(
            f"{unreachable} station(s) cannot reach the incident on the current "
            "network; the route set is incomplete by that much")
    if rows:
        best = rows[0]
        res.add("best_response_time_s", best["response_time_s"], "seconds")
        res.add("best_response_time_min", best["response_time_min"], "minutes")
        res.add("best_distance_m", best["distance_m"], "m")
        res.add("meets_response_target", 1 if best["within_target"] else 0, "bool")
        if not best["within_target"]:
            res.warnings.append(
                f"fastest unit arrives in {best['response_time_min']:.1f} min, "
                f"outside the {response_target_seconds / 60.0:.0f} min target")
    else:
        res.warnings.append(
            "no station can reach this incident — it is cut off on the current "
            "network")
    return res


def compare_routes(
    base_graph: nx.DiGraph,
    degraded_graph: nx.DiGraph,
    incident_point: Any,
    stations: Sequence[Any],
    provenance: Provenance,
    turnout_seconds: float = DEFAULT_TURNOUT_SECONDS,
    response_target_seconds: float = 480.0,
) -> EngineResult:
    """Normal vs degraded response for the same incident.

    The delta is the point: it quantifies what the disruption costs in minutes.
    """
    before = route_to_incident(
        base_graph, incident_point, stations, provenance, top_n=1,
        turnout_seconds=turnout_seconds,
        response_target_seconds=response_target_seconds)
    after = route_to_incident(
        degraded_graph, incident_point, stations, provenance, top_n=1,
        turnout_seconds=turnout_seconds,
        response_target_seconds=response_target_seconds)

    res = EngineResult(result_type="emergency_route_comparison",
                       provenance=provenance)
    b = before.records[0] if before.records else None
    a = after.records[0] if after.records else None

    res.records = [r for r in (
        dict(b or {}, scenario="baseline") if b else None,
        dict(a or {}, scenario="degraded") if a else None,
    ) if r]

    if b:
        res.add("baseline_response_s", b["response_time_s"], "seconds")
    if a:
        res.add("degraded_response_s", a["response_time_s"], "seconds")
    if b and a:
        delta = a["response_time_s"] - b["response_time_s"]
        res.add("delay_s", round(delta, 1), "seconds")
        res.add("delay_min", round(delta / 60.0, 2), "minutes")
        res.add("delay_pct",
                round(100.0 * delta / b["response_time_s"], 1)
                if b["response_time_s"] else 0.0, "percent")
        if b["within_target"] and not a["within_target"]:
            res.warnings.append(
                "the disruption pushes this incident outside the response "
                "target; it was inside before")
        if a["station_id"] != b["station_id"]:
            res.warnings.append(
                f"primary responder changes from {b['station_name']} to "
                f"{a['station_name']} under these conditions")
    elif b and not a:
        res.warnings.append(
            "the incident becomes UNREACHABLE under these conditions; "
            "no unit can arrive by road")
        res.add("cut_off", 1, "bool")
    return res
