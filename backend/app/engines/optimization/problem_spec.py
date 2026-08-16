"""Declarative optimization problem specifications. ARCHITECTURE §15.

Engines consume a spec and return machine-readable results. Solver seeds and
limits are part of the spec so a run is reproducible (§25).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Sequence


@dataclass
class SolveOptions:
    time_limit_seconds: float = 30.0
    seed: int = 42
    relative_gap: float = 0.0
    workers: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FacilityLocationProblem:
    """Choose p sites from candidates to serve demand points.

    cost_matrix[i][j] = travel time/distance from demand i to candidate j.
    None marks an unreachable pair.
    """

    candidate_ids: Sequence[str]
    demand_ids: Sequence[str]
    demand_weights: Sequence[float]
    cost_matrix: Sequence[Sequence[float | None]]
    p: int = 1
    capacities: Sequence[float] | None = None
    max_cost: float | None = None
    fixed_costs: Sequence[float] | None = None
    must_open: Sequence[str] = ()
    must_close: Sequence[str] = ()

    def validate(self) -> None:
        n_d, n_c = len(self.demand_ids), len(self.candidate_ids)
        if n_c == 0:
            raise ValueError("no candidates supplied")
        if n_d == 0:
            raise ValueError("no demand points supplied")
        if len(self.demand_weights) != n_d:
            raise ValueError("demand_weights length must match demand_ids")
        if len(self.cost_matrix) != n_d:
            raise ValueError("cost_matrix rows must match demand_ids")
        for row in self.cost_matrix:
            if len(row) != n_c:
                raise ValueError("cost_matrix columns must match candidate_ids")
        if self.capacities is not None and len(self.capacities) != n_c:
            raise ValueError("capacities length must match candidate_ids")
        if not 1 <= self.p <= n_c:
            raise ValueError(f"p must be between 1 and {n_c}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidates": len(self.candidate_ids),
            "demand_points": len(self.demand_ids),
            "p": self.p,
            "capacitated": self.capacities is not None,
            "max_cost": self.max_cost,
        }


@dataclass
class AllocationProblem:
    """Distribute a limited budget/capacity across zones."""

    zone_ids: Sequence[str]
    demand: Sequence[float]
    unit_cost: Sequence[float]
    benefit: Sequence[float]
    budget: float
    min_units: Sequence[int] | None = None
    max_units: Sequence[int] | None = None

    def validate(self) -> None:
        n = len(self.zone_ids)
        if n == 0:
            raise ValueError("no zones supplied")
        for name, seq in [("demand", self.demand), ("unit_cost", self.unit_cost),
                          ("benefit", self.benefit)]:
            if len(seq) != n:
                raise ValueError(f"{name} length must match zone_ids")
        if self.budget <= 0:
            raise ValueError("budget must be positive")
