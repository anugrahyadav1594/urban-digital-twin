"""Service layer: PostGIS -> deterministic engines -> persisted results.

ARCHITECTURE §5. Services own orchestration and versioning; they contain no
spatial mathematics of their own, delegating all computation to the engines.
"""
from .accessibility_service import (
    analyze_accessibility, analyze_capacity, analyze_emergency_response,
    analyze_resilience, compute_service_area,
)
from .context import AnalysisContext
from .optimization_service import optimize_facility_locations
from .planning_service import find_best_sites
from .scenario_service import compare, evaluate_scenario, resolve

__all__ = [
    "AnalysisContext",
    "find_best_sites",
    "analyze_accessibility", "analyze_emergency_response",
    "compute_service_area", "analyze_capacity", "analyze_resilience",
    "optimize_facility_locations",
    "resolve", "evaluate_scenario", "compare",
]
