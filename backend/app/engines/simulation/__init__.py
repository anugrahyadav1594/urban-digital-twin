"""Simulation engine. ARCHITECTURE §17."""
from .population_growth import project_population, GrowthAssumptions
from .infrastructure_demand import demand_vs_capacity, SERVICE_STANDARDS
from .flood_exposure import flood_exposure
from .environmental_impact import environmental_impact
from .resilience import resilience_analysis
from .disaster import (HAZARD_TYPES, MEASURES, Hazard, build_hazard,
                       compare_measures, simulate_disaster)

__all__ = [
    "project_population", "GrowthAssumptions",
    "demand_vs_capacity", "SERVICE_STANDARDS",
    "flood_exposure", "environmental_impact", "resilience_analysis",
    "HAZARD_TYPES", "MEASURES", "Hazard", "build_hazard",
    "compare_measures", "simulate_disaster",
]
