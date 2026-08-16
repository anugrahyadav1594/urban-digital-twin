"""Network and service resilience. ARCHITECTURE §17.1."""
from __future__ import annotations

from typing import Any, Sequence

import networkx as nx

from ..contracts import EngineResult, Provenance

ALGORITHM = "simulation.resilience"
ALGORITHM_VERSION = "0.1.0"


def resilience_analysis(
    G: nx.DiGraph,
    provenance: Provenance,
    facilities: Sequence[Any] = (),
    max_critical_nodes: int = 25,
) -> EngineResult:
    """Connectivity, redundancy and single-point-of-failure analysis."""
    res = EngineResult(result_type="resilience", provenance=provenance)

    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()
    res.add("nodes", n_nodes, "count")
    res.add("edges", n_edges, "count")

    if n_nodes == 0:
        res.warnings.append("empty graph; resilience undefined")
        return res

    UG = G.to_undirected()
    components = list(nx.connected_components(UG))
    largest = max(components, key=len)

    res.add("connected_components", len(components), "count")
    res.add("largest_component_share", round(len(largest) / n_nodes, 4), "ratio")

    # Articulation points: removal disconnects the network.
    cut_nodes = list(nx.articulation_points(UG)) if n_nodes > 2 else []
    bridges = list(nx.bridges(UG)) if n_nodes > 1 else []

    res.add("articulation_points", len(cut_nodes), "count")
    res.add("bridge_edges", len(bridges), "count")
    res.add("redundancy_index",
            round(1.0 - (len(bridges) / n_edges), 4) if n_edges else None, "index")

    # Average degree is a coarse proxy for route choice.
    avg_degree = (2.0 * UG.number_of_edges() / n_nodes) if n_nodes else 0.0
    res.add("average_degree", round(avg_degree, 3), "edges_per_node")

    res.records.append({
        "critical_nodes": [list(map(float, n)) for n in cut_nodes[:max_critical_nodes]],
        "critical_edge_count": len(bridges),
    })

    isolated_facilities = []
    for f in facilities:
        from ..network.routing import nearest_node
        nn = nearest_node(G, f.geometry)
        if nn is None or nn not in largest:
            isolated_facilities.append(str(f.id))
    if isolated_facilities:
        res.add("facilities_off_main_network", len(isolated_facilities), "count")
        res.records.append({"isolated_facility_ids": isolated_facilities})
        res.warnings.append(
            f"{len(isolated_facilities)} facilities are not on the largest "
            "connected component"
        )

    if len(components) > 1:
        res.warnings.append(
            f"network is fragmented into {len(components)} components"
        )
    res.provenance = provenance.with_assumptions(
        "resilience computed on the undirected road graph",
        "no hazard-specific failure probabilities applied",
    )
    return res
