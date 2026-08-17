"""Population projection. ARCHITECTURE §17.1.

Deterministic compound growth. Assumptions are always emitted with results so
projections are never mistaken for observations (§22).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from ..contracts import EngineResult, Provenance

ALGORITHM = "simulation.population_growth"
ALGORITHM_VERSION = "0.1.0"


@dataclass
class GrowthAssumptions:
    """Growth configuration. rate is annual and fractional (0.025 = 2.5%/yr)."""

    base_year: int
    horizon_year: int
    annual_rate: float = 0.02
    zone_rates: Mapping[str, float] = field(default_factory=dict)
    capacity_ceiling: Mapping[str, float] = field(default_factory=dict)

    @property
    def years(self) -> int:
        return max(0, self.horizon_year - self.base_year)

    def rate_for(self, zone_id: str) -> float:
        return float(self.zone_rates.get(str(zone_id), self.annual_rate))

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_year": self.base_year,
            "horizon_year": self.horizon_year,
            "years": self.years,
            "annual_rate": self.annual_rate,
            "zone_specific_rates": dict(self.zone_rates),
        }


def project_population(
    zones: Sequence[Any],
    assumptions: GrowthAssumptions,
    provenance: Provenance,
) -> EngineResult:
    """Project population per zone to the horizon year."""
    res = EngineResult(result_type="population_projection", provenance=provenance)

    if assumptions.horizon_year < assumptions.base_year:
        res.warnings.append("horizon_year precedes base_year; no projection run")
        return res

    n = assumptions.years
    base_total = 0.0
    proj_total = 0.0

    for z in zones:
        p0 = float(z.population or 0.0)
        r = assumptions.rate_for(z.id)
        p1 = p0 * ((1.0 + r) ** n)

        ceiling = assumptions.capacity_ceiling.get(str(z.id))
        capped = False
        if ceiling is not None and p1 > float(ceiling):
            p1 = float(ceiling)
            capped = True

        area_km2 = (z.geometry.area / 1_000_000.0) if z.geometry is not None else None
        base_total += p0
        proj_total += p1

        res.records.append({
            "zone_id": str(z.id),
            "population_base": round(p0, 1),
            "population_projected": round(p1, 1),
            "absolute_growth": round(p1 - p0, 1),
            "growth_ratio": round(p1 / p0, 4) if p0 > 0 else None,
            "annual_rate": r,
            "density_projected": round(p1 / area_km2, 1)
            if area_km2 and area_km2 > 0 else None,
            "capacity_capped": capped,
        })

    res.add("population_base", round(base_total, 1), "persons")
    res.add("population_projected", round(proj_total, 1), "persons")
    res.add("absolute_growth", round(proj_total - base_total, 1), "persons")
    res.add("growth_ratio",
            round(proj_total / base_total, 4) if base_total else None, "ratio")
    res.add("horizon_years", n, "years")

    res.provenance = provenance.with_assumptions(
        f"compound annual growth at {assumptions.annual_rate:.2%} unless a "
        "zone-specific rate is set",
        f"projection horizon {assumptions.base_year}->{assumptions.horizon_year} "
        f"({n} years)",
        "no migration, mortality or land-capacity model applied",
    )
    return res
