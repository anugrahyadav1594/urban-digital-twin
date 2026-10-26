"""Disaster-aware point-to-point route comparison engine.

Answers the core NagarX research question:
  "When a road or urban area becomes affected by a simulated disaster,
   how does the available route between two locations change?"

Logical model:
  - Road intersections and segment endpoints are directed graph nodes (projected metres).
  - Navigable road segments are directed edges with baseline distance (m) and
    nominal free-flow travel time (s) derived from OSM road class / speed limit.
  - Scenario data identifies affected edges via spatial intersection with a
    simulated hazard polygon/buffer and/or explicit road segment IDs.
  - Baseline route minimizes baseline cost (travel time or distance) on G using
    Dijkstra's algorithm.
  - Hazard-aware route uses the same origin node, destination node, and base
    network G, removing closed/impassable edges and/or multiplying penalized
    edge costs by an explicitly defined factor (>= 1.0).
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

import networkx as nx
from shapely.geometry import LineString, Point

from .routing import nearest_node_in, routable_core

ALGORITHM = "network.disaster_route_compare"
ALGORITHM_VERSION = "1.0.0"

SUPPORTED_SCENARIO_TYPES = {"flood", "fire", "road_blockage", "affected_zone"}
SUPPORTED_SEVERITY_MODES = {"closed", "penalized"}
SUPPORTED_COST_METRICS = {"time", "distance"}

MAX_SNAP_DISTANCE_M = 2500.0
WARN_SNAP_DISTANCE_M = 150.0


@dataclass(frozen=True)
class DisasterScenarioSpec:
    """Validated specification of a simulated hazard scenario."""

    name: str
    scenario_type: str = "flood"
    active: bool = True
    severity_mode: str = "closed"          # "closed" | "penalized"
    penalty_multiplier: float = 3.0        # must be >= 1.0
    hazard_geometry: Any = None            # Shapely Polygon/MultiPolygon in analysis CRS
    affected_road_ids: tuple[str, ...] = ()
    slowed_road_ids: tuple[str, ...] = ()

    def validate(self) -> None:
        if self.scenario_type not in SUPPORTED_SCENARIO_TYPES:
            raise ValueError(
                f"Unsupported scenario type '{self.scenario_type}'. "
                f"Expected one of {sorted(SUPPORTED_SCENARIO_TYPES)}."
            )
        if self.severity_mode not in SUPPORTED_SEVERITY_MODES:
            raise ValueError(
                f"Unsupported severity mode '{self.severity_mode}'. "
                f"Expected one of {sorted(SUPPORTED_SEVERITY_MODES)}."
            )
        if not math.isfinite(self.penalty_multiplier) or self.penalty_multiplier < 1.0:
            raise ValueError(
                f"Invalid penalty multiplier ({self.penalty_multiplier}); "
                "penalty multiplier must be a finite number >= 1.0."
            )
        if self.hazard_geometry is not None:
            if getattr(self.hazard_geometry, "is_empty", True):
                raise ValueError("Simulated hazard geometry is empty.")
            if not getattr(self.hazard_geometry, "is_valid", True):
                raise ValueError("Simulated hazard geometry is self-intersecting or invalid.")


def _validate_base_graph_costs(G: nx.DiGraph) -> None:
    """Reject negative, NaN, or non-positive baseline edge costs."""
    for u, v, data in G.edges(data=True):
        length = float(data.get("length", -1.0))
        travel_s = float(data.get("time", -1.0))
        if not math.isfinite(length) or length <= 0.0:
            raise ValueError(f"Invalid non-positive edge length on ({u} -> {v}): {length}")
        if not math.isfinite(travel_s) or travel_s <= 0.0:
            raise ValueError(f"Invalid non-positive edge travel time on ({u} -> {v}): {travel_s}")


def classify_affected_edges(
    G: nx.DiGraph,
    scenario: DisasterScenarioSpec,
) -> tuple[set[tuple[Any, Any]], set[tuple[Any, Any]], set[str], set[str]]:
    """Identify closed and penalized directed edges in G under `scenario`.

    Returns:
      (closed_edges, penalized_edges, closed_road_ids, penalized_road_ids)
    """
    scenario.validate()
    closed_edges: set[tuple[Any, Any]] = set()
    penalized_edges: set[tuple[Any, Any]] = set()
    closed_road_ids: set[str] = set()
    penalized_road_ids: set[str] = set()

    if not scenario.active:
        return closed_edges, penalized_edges, closed_road_ids, penalized_road_ids

    explicit_affected = {str(r) for r in scenario.affected_road_ids if str(r)}
    explicit_slowed = {str(r) for r in scenario.slowed_road_ids if str(r)}
    hz = scenario.hazard_geometry

    for u, v, data in G.edges(data=True):
        raw_id = str(data.get("road_id", ""))
        parent_id = raw_id.split("#", 1)[0]
        src_str = str(data.get("source") or "")
        osm_tag = src_str.split(":", 1)[1] if "osm_way_" in src_str and ":" in src_str else ""

        candidate_ids = {cid for cid in (parent_id, raw_id, osm_tag) if cid}
        in_explicit_affected = bool(candidate_ids & explicit_affected)
        in_explicit_slowed = bool(candidate_ids & explicit_slowed)
        in_geom = False
        if hz is not None:
            seg = LineString([u, v])
            in_geom = bool(hz.intersects(seg))

        report_id = osm_tag or parent_id
        is_primary_hit = in_explicit_affected or in_geom
        if is_primary_hit:
            if scenario.severity_mode == "closed":
                closed_edges.add((u, v))
                if report_id:
                    closed_road_ids.add(report_id)
            else:
                penalized_edges.add((u, v))
                if report_id:
                    penalized_road_ids.add(report_id)
        elif in_explicit_slowed:
            penalized_edges.add((u, v))
            if report_id:
                penalized_road_ids.add(report_id)

    return closed_edges, penalized_edges, closed_road_ids, penalized_road_ids


def build_hazard_aware_graph(
    G: nx.DiGraph,
    closed_edges: set[tuple[Any, Any]],
    penalized_edges: set[tuple[Any, Any]],
    cost_metric: str,
    penalty_multiplier: float,
) -> nx.DiGraph:
    """Create a shallow graph copy with closed edges removed and penalties applied."""
    if cost_metric not in SUPPORTED_COST_METRICS:
        raise ValueError(f"Unsupported cost metric '{cost_metric}'.")
    if not math.isfinite(penalty_multiplier) or penalty_multiplier < 1.0:
        raise ValueError("Penalty multiplier must be >= 1.0.")

    base_attr = "time" if cost_metric == "time" else "length"
    H = nx.DiGraph()
    H.add_nodes_from(G.nodes(data=True))

    for u, v, data in G.edges(data=True):
        if (u, v) in closed_edges:
            continue
        edge_data = dict(data)
        base_cost = float(edge_data[base_attr])
        if (u, v) in penalized_edges:
            edge_data["effective_cost"] = base_cost * penalty_multiplier
        else:
            edge_data["effective_cost"] = base_cost
        H.add_edge(u, v, **edge_data)

    return H


def _summarize_path(
    G_ref: nx.DiGraph,
    node_path: Sequence[tuple[float, float]] | None,
    affected_edges: set[tuple[Any, Any]],
    snap_origin_m: float,
    snap_dest_m: float,
) -> dict[str, Any]:
    if node_path is None:
        return {
            "feasible": False,
            "path": [],
            "distance_m": None,
            "travel_time_s": None,
            "segment_count": 0,
            "affected_segment_count": 0,
            "affected_road_ids": [],
            "exposed_distance_m": 0.0,
            "snap_origin_m": round(snap_origin_m, 1),
            "snap_destination_m": round(snap_dest_m, 1),
        }

    total_dist = 0.0
    total_time = 0.0
    affected_seg_count = 0
    exposed_dist = 0.0
    hit_road_ids: list[str] = []
    seen_rids: set[str] = set()

    for a, b in zip(node_path[:-1], node_path[1:]):
        ed = G_ref.get_edge_data(a, b) or {}
        seg_len = float(ed.get("length", 0.0))
        seg_time = float(ed.get("time", 0.0))
        total_dist += seg_len
        total_time += seg_time
        if (a, b) in affected_edges:
            affected_seg_count += 1
            exposed_dist += seg_len
            rid = str(ed.get("road_id", "")).split("#", 1)[0]
            if rid and rid not in seen_rids:
                seen_rids.add(rid)
                hit_road_ids.append(rid)

    return {
        "feasible": True,
        "path": [[float(x), float(y)] for x, y in node_path],
        "distance_m": round(total_dist, 1),
        "travel_time_s": round(total_time, 1),
        "segment_count": max(0, len(node_path) - 1),
        "affected_segment_count": affected_seg_count,
        "affected_road_ids": hit_road_ids,
        "exposed_distance_m": round(exposed_dist, 1),
        "snap_origin_m": round(snap_origin_m, 1),
        "snap_destination_m": round(snap_dest_m, 1),
    }


def compare_disaster_routes(
    G: nx.DiGraph,
    origin_point: Point,
    destination_point: Point,
    scenario: DisasterScenarioSpec,
    cost_metric: str = "time",
    max_snap_m: float = MAX_SNAP_DISTANCE_M,
) -> dict[str, Any]:
    """Compute and compare baseline and hazard-aware routes on `G`.

    Raises ValueError on invalid origin, destination, cost metric, or scenario.
    """
    t0 = time.perf_counter()

    if G is None or G.number_of_nodes() == 0 or G.number_of_edges() == 0:
        raise ValueError("Road network graph is empty; cannot compute routes.")
    if cost_metric not in SUPPORTED_COST_METRICS:
        raise ValueError(
            f"Unsupported cost metric '{cost_metric}'. Expected 'time' or 'distance'."
        )
    if origin_point is None or origin_point.is_empty or not (
        math.isfinite(origin_point.x) and math.isfinite(origin_point.y)
    ):
        raise ValueError("Origin point is missing or has invalid coordinates.")
    if destination_point is None or destination_point.is_empty or not (
        math.isfinite(destination_point.x) and math.isfinite(destination_point.y)
    ):
        raise ValueError("Destination point is missing or has invalid coordinates.")

    scenario.validate()
    _validate_base_graph_costs(G)

    core = routable_core(G)
    if not core:
        raise ValueError("Road network has no connected routable component.")

    orig_node, orig_snap_m = nearest_node_in(G, origin_point, core)
    dest_node, dest_snap_m = nearest_node_in(G, destination_point, core)
    if orig_node is None or dest_node is None:
        raise ValueError("Could not snap origin or destination onto the road network.")
    if orig_snap_m > max_snap_m:
        raise ValueError(
            f"Origin is {orig_snap_m:.0f} m from the nearest road in this study area "
            f"(maximum snap distance is {max_snap_m:.0f} m)."
        )
    if dest_snap_m > max_snap_m:
        raise ValueError(
            f"Destination is {dest_snap_m:.0f} m from the nearest road in this study area "
            f"(maximum snap distance is {max_snap_m:.0f} m)."
        )
    if orig_node == dest_node:
        raise ValueError(
            "Origin and destination map to the same road intersection. "
            "Select two distinct locations."
        )

    closed_edges, penalized_edges, closed_rids, penalized_rids = classify_affected_edges(
        G, scenario
    )
    all_affected_edges = closed_edges | penalized_edges

    base_weight = "time" if cost_metric == "time" else "length"
    try:
        base_nodes = nx.dijkstra_path(G, orig_node, dest_node, weight=base_weight)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        base_nodes = None

    H = build_hazard_aware_graph(
        G,
        closed_edges=closed_edges,
        penalized_edges=penalized_edges,
        cost_metric=cost_metric,
        penalty_multiplier=scenario.penalty_multiplier,
    )
    try:
        alt_nodes = nx.dijkstra_path(H, orig_node, dest_node, weight="effective_cost")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        alt_nodes = None

    baseline_summary = _summarize_path(
        G, base_nodes, all_affected_edges, orig_snap_m, dest_snap_m
    )
    alt_summary = _summarize_path(
        G, alt_nodes, all_affected_edges, orig_snap_m, dest_snap_m
    )

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    routes_identical = bool(
        base_nodes is not None and alt_nodes is not None and base_nodes == alt_nodes
    )

    dist_delta_m: float | None = None
    dist_delta_pct: float | None = None
    time_delta_s: float | None = None
    time_delta_pct: float | None = None
    avoided_segments: int | None = None
    exposure_reduction_m: float | None = None

    if baseline_summary["feasible"] and alt_summary["feasible"]:
        b_d = float(baseline_summary["distance_m"])
        a_d = float(alt_summary["distance_m"])
        b_t = float(baseline_summary["travel_time_s"])
        a_t = float(alt_summary["travel_time_s"])
        dist_delta_m = round(a_d - b_d, 1)
        dist_delta_pct = round(((a_d - b_d) / b_d) * 100.0, 1) if b_d > 0 else 0.0
        time_delta_s = round(a_t - b_t, 1)
        time_delta_pct = round(((a_t - b_t) / b_t) * 100.0, 1) if b_t > 0 else 0.0
        avoided_segments = int(
            baseline_summary["affected_segment_count"] - alt_summary["affected_segment_count"]
        )
        exposure_reduction_m = round(
            float(baseline_summary["exposed_distance_m"]) - float(alt_summary["exposed_distance_m"]),
            1,
        )

    warnings: list[str] = []
    if orig_snap_m > WARN_SNAP_DISTANCE_M:
        warnings.append(
            f"Origin was snapped {orig_snap_m:.0f} m to the nearest connected road node."
        )
    if dest_snap_m > WARN_SNAP_DISTANCE_M:
        warnings.append(
            f"Destination was snapped {dest_snap_m:.0f} m to the nearest connected road node."
        )
    if scenario.active and not all_affected_edges:
        warnings.append(
            "The active scenario does not intersect any navigable road segments in the study area."
        )

    summary_text = _build_explanation(
        scenario=scenario,
        baseline=baseline_summary,
        alternative=alt_summary,
        routes_identical=routes_identical,
        dist_delta_m=dist_delta_m,
        time_delta_s=time_delta_s,
        closed_edge_count=len(closed_edges),
        penalized_edge_count=len(penalized_edges),
    )

    assumptions = [
        f"Shortest paths computed with Dijkstra's algorithm minimizing {'nominal free-flow travel time' if cost_metric == 'time' else 'network distance'}.",
        "Travel time is derived from road-class speed limits (or OSM maxspeed tags where present) without live traffic congestion or turn delays.",
        (
            "Affected segments are excluded as impassable in the hazard-aware graph."
            if scenario.severity_mode == "closed"
            else f"Affected segments remain traversable with a {scenario.penalty_multiplier:.1f}x traversal cost penalty."
        ),
        "Affected-segment exposure measures the cumulative length (m) of traversed graph edges intersecting the simulated hazard.",
    ]

    limitations = [
        "Hazards are simulated geometric overlays or explicit segment selections, not real-time sensor feeds or hydrodynamic/fire-spread solver outputs.",
        "Avoiding simulated hazard segments indicates route feasibility on the modelled graph; it does not certify real-world physical safety.",
        "Unmapped private lanes, footpaths, and temporary field obstructions are outside the road graph.",
    ]

    return {
        "baseline_route": baseline_summary,
        "hazard_aware_route": alt_summary,
        "affected_network": {
            "closed_edge_count": len(closed_edges),
            "penalized_edge_count": len(penalized_edges),
            "closed_road_ids": sorted(closed_rids),
            "penalized_road_ids": sorted(penalized_rids),
            "closed_segments_projected": [
                [[float(u[0]), float(u[1])], [float(v[0]), float(v[1])]]
                for u, v in list(closed_edges)[:500]
            ],
            "penalized_segments_projected": [
                [[float(u[0]), float(u[1])], [float(v[0]), float(v[1])]]
                for u, v in list(penalized_edges)[:500]
            ],
        },
        "comparison": {
            "baseline_feasible": baseline_summary["feasible"],
            "alternative_feasible": alt_summary["feasible"],
            "routes_identical": routes_identical,
            "distance_delta_m": dist_delta_m,
            "distance_delta_pct": dist_delta_pct,
            "time_delta_s": time_delta_s,
            "time_delta_pct": time_delta_pct,
            "avoided_segments": avoided_segments,
            "exposure_reduction_m": exposure_reduction_m,
            "summary": summary_text,
            "assumptions": assumptions,
            "limitations": limitations,
            "warnings": warnings,
        },
        "computation_time_ms": elapsed_ms,
    }


def _build_explanation(
    scenario: DisasterScenarioSpec,
    baseline: dict[str, Any],
    alternative: dict[str, Any],
    routes_identical: bool,
    dist_delta_m: float | None,
    time_delta_s: float | None,
    closed_edge_count: int,
    penalized_edge_count: int,
) -> str:
    if not baseline["feasible"]:
        return (
            "No feasible baseline route exists between the selected origin and destination "
            "on the base road network."
        )
    if not scenario.active:
        return (
            f"Scenario '{scenario.name}' is inactive. Both baseline and hazard-aware calculations "
            f"follow the same {baseline['distance_m'] / 1000.0:.2f} km path with 0 m simulated exposure."
        )
    if not alternative["feasible"]:
        return (
            f"No feasible route found under the current scenario ('{scenario.name}'). "
            f"The baseline route ({baseline['distance_m'] / 1000.0:.2f} km) traverses "
            f"{baseline['affected_segment_count']} affected segment(s) "
            f"({baseline['exposed_distance_m']:.0f} m simulated exposure), and removing the "
            f"{closed_edge_count} impassable directed edge(s) disconnects all navigable paths "
            "between origin and destination."
        )
    if routes_identical:
        if baseline["affected_segment_count"] == 0:
            return (
                f"The baseline route ({baseline['distance_m'] / 1000.0:.2f} km) does not intersect "
                f"any of the {closed_edge_count + penalized_edge_count} directed edge(s) affected by "
                f"'{scenario.name}', so no detour is required."
            )
        return (
            f"Under penalty mode ({scenario.penalty_multiplier:.1f}x), the baseline route "
            f"({baseline['distance_m'] / 1000.0:.2f} km) remains lower-cost than any available detour, "
            f"retaining {baseline['exposed_distance_m']:.0f} m of simulated hazard exposure across "
            f"{baseline['affected_segment_count']} segment(s)."
        )

    detour_km = (dist_delta_m or 0.0) / 1000.0
    detour_min = (time_delta_s or 0.0) / 60.0
    sign_km = "+" if detour_km >= 0 else ""
    sign_min = "+" if detour_min >= 0 else ""
    return (
        f"The baseline route is shorter ({baseline['distance_m'] / 1000.0:.2f} km, "
        f"{baseline['travel_time_s'] / 60.0:.1f} min) but traverses "
        f"{baseline['affected_segment_count']} simulated hazard-affected segment(s) "
        f"({baseline['exposed_distance_m']:.0f} m simulated exposure). "
        f"Under '{scenario.name}', the hazard-aware alternative detours around the affected "
        f"corridor ({alternative['distance_m'] / 1000.0:.2f} km, "
        f"{alternative['travel_time_s'] / 60.0:.1f} min; {sign_km}{detour_km:.2f} km / "
        f"{sign_min}{detour_min:.1f} min), reducing simulated affected-segment exposure from "
        f"{baseline['exposed_distance_m']:.0f} m to {alternative['exposed_distance_m']:.0f} m."
    )
