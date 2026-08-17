"""Deterministic domain engines. ARCHITECTURE §12-§17, §24.

Engines are pure functions of versioned inputs. They never touch the database,
the API or the LLM layer; callers pass domain records in and receive
EngineResult objects carrying full provenance.
"""
from .contracts import (
    Building, EngineResult, EntityType, Facility, Metric, Operation, Parcel,
    PlanningConstraint, PopulationZone, Provenance, Road, Scenario,
    ScenarioChange, Severity,
)

__all__ = [
    "Building", "EngineResult", "EntityType", "Facility", "Metric",
    "Operation", "Parcel", "PlanningConstraint", "PopulationZone",
    "Provenance", "Road", "Scenario", "ScenarioChange", "Severity",
]
