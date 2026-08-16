"""Optimization engine. ARCHITECTURE §15."""
from .problem_spec import FacilityLocationProblem, AllocationProblem, SolveOptions
from .facility_location import solve_facility_location, solve_max_coverage
from .allocation import solve_allocation
from .multi_objective import pareto_front, weighted_scalarization

__all__ = [
    "FacilityLocationProblem", "AllocationProblem", "SolveOptions",
    "solve_facility_location", "solve_max_coverage", "solve_allocation",
    "pareto_front", "weighted_scalarization",
]
