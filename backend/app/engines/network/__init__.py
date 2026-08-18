"""Network / accessibility engine. ARCHITECTURE §13."""
from .graph_builder import build_graph, graph_signature, apply_road_deltas
from .routing import shortest_path, travel_time, travel_time_matrix, nearest_node
from .emergency_routing import route_to_incident, degrade_graph, compare_routes
from .service_area import service_area_nodes, service_area_polygon, isochrone
from .accessibility import (
    accessibility_metrics,
    population_to_facility,
    emergency_response,
    compare_accessibility,
)

__all__ = [
    "build_graph", "graph_signature", "apply_road_deltas",
    "shortest_path", "travel_time", "travel_time_matrix", "nearest_node",
    "route_to_incident", "degrade_graph", "compare_routes",
    "service_area_nodes", "service_area_polygon", "isochrone",
    "accessibility_metrics", "population_to_facility", "emergency_response",
    "compare_accessibility",
]
