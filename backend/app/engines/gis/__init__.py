"""GIS / spatial analysis engine. ARCHITECTURE §12."""
from .overlay import intersects_any, containment, spatial_join, overlay_area_fraction
from .buffers import buffer_geometry, buffered_union, exclusion_mask
from .distance import (
    nearest_facility,
    k_nearest_facilities,
    distance_matrix,
    min_distance_to_any,
)
from .aggregation import aggregate_by_zone, population_within, coverage_ratio
from .constraints import ConstraintReport, evaluate_constraints, filter_by_constraints

__all__ = [
    "intersects_any", "containment", "spatial_join", "overlay_area_fraction",
    "buffer_geometry", "buffered_union", "exclusion_mask",
    "nearest_facility", "k_nearest_facilities", "distance_matrix",
    "min_distance_to_any",
    "aggregate_by_zone", "population_within", "coverage_ratio",
    "ConstraintReport", "evaluate_constraints", "filter_by_constraints",
]
