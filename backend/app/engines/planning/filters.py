"""Hard constraint filtering. ARCHITECTURE §14.1, §14.2.

Every elimination is recorded with the rule, threshold and observed value.
Nothing is dropped silently.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Sequence

from ..gis.constraints import ConstraintReport, evaluate_constraints


@dataclass
class SiteRequirements:
    """Input specification for facility placement (§14.1)."""

    facility_type: str
    capacity: float | None = None
    required_area: float | None = None          # m^2
    max_travel_time: float | None = None        # seconds
    min_distance_same_type: float | None = None  # m
    max_distance_to_demand: float | None = None  # m
    allowed_zoning: tuple[str, ...] = ()
    allowed_status: tuple[str, ...] = ("vacant", "under_development")
    max_slope: float | None = None              # degrees
    max_flood_risk: float | None = None         # 0..1
    scoring_profile: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["allowed_zoning"] = list(self.allowed_zoning)
        d["allowed_status"] = list(self.allowed_status)
        return d


def hard_filter(
    parcels: Sequence[Any],
    requirements: SiteRequirements,
    constraints: Sequence[Any] = (),
) -> tuple[list[Any], list[ConstraintReport]]:
    """Apply disqualifying rules. Returns (survivors, all reports)."""
    reports = [
        evaluate_constraints(
            p, constraints,
            min_area=requirements.required_area,
            max_slope=requirements.max_slope,
            max_flood_risk=requirements.max_flood_risk,
            allowed_zoning=requirements.allowed_zoning or None,
            allowed_status=requirements.allowed_status or None,
        )
        for p in parcels
    ]
    survivors = [p for p, r in zip(parcels, reports) if r.passed]
    return survivors, reports
