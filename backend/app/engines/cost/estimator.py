"""Transparent cost estimation from configured unit rates.

ARCHITECTURE §19: estimates are explicitly prototype-level and always travel
with their assumption set. Rates are configuration, never hardcoded logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from ..contracts import EngineResult, Provenance

ALGORITHM = "cost.estimator"
ALGORITHM_VERSION = "0.1.0"


@dataclass(frozen=True)
class CostProfile:
    """Versioned unit-rate table. Currency is caller-defined and recorded."""

    name: str
    version: str
    currency: str = "INR"
    rates: Mapping[str, float] = field(default_factory=dict)
    contingency_rate: float = 0.15
    escalation_rate: float = 0.0

    def rate(self, item: str) -> float | None:
        return self.rates.get(item)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "version": self.version, "currency": self.currency,
            "contingency_rate": self.contingency_rate,
            "escalation_rate": self.escalation_rate,
            "rates": dict(self.rates),
        }


DEFAULT_COST_PROFILE = CostProfile(
    name="prototype-in",
    version="0.1.0",
    currency="INR",
    rates={
        "land_acquisition_per_m2": 6000.0,
        "road_per_m_local": 12000.0,
        "road_per_m_collector": 22000.0,
        "road_per_m_arterial": 38000.0,
        "hospital_per_bed": 4_500_000.0,
        "school_per_seat": 85_000.0,
        "fire_station_fixed": 65_000_000.0,
        "site_preparation_per_m2": 900.0,
        "drainage_per_m": 4500.0,
    },
    contingency_rate=0.15,
)


def estimate_cost(
    quantities: Mapping[str, float],
    provenance: Provenance,
    profile: CostProfile | None = None,
) -> EngineResult:
    """Itemise cost from quantities keyed by rate name.

    Unknown keys are reported as warnings rather than silently priced at zero.
    """
    prof = profile or DEFAULT_COST_PROFILE
    res = EngineResult(result_type="cost_estimate", provenance=provenance)

    subtotal = 0.0
    unpriced: list[str] = []

    for item, qty in quantities.items():
        rate = prof.rate(item)
        if rate is None:
            unpriced.append(item)
            res.records.append({
                "item": item, "quantity": qty, "unit_rate": None,
                "amount": None, "priced": False,
            })
            continue
        amount = float(qty) * float(rate)
        subtotal += amount
        res.records.append({
            "item": item, "quantity": round(float(qty), 3),
            "unit_rate": rate, "amount": round(amount, 2), "priced": True,
        })

    contingency = subtotal * prof.contingency_rate
    escalation = (subtotal + contingency) * prof.escalation_rate
    total = subtotal + contingency + escalation

    res.add("subtotal", round(subtotal, 2), prof.currency)
    res.add("contingency", round(contingency, 2), prof.currency)
    res.add("escalation", round(escalation, 2), prof.currency)
    res.add("total_cost", round(total, 2), prof.currency)
    res.add("line_items_priced",
            sum(1 for r in res.records if r["priced"]), "count")

    res.artifacts.append({
        "type": "cost_profile", "name": prof.name, "version": prof.version,
        "currency": prof.currency,
    })
    if unpriced:
        res.warnings.append(
            "no unit rate configured for: " + ", ".join(sorted(unpriced))
        )
    res.provenance = provenance.with_assumptions(
        f"unit rates from cost profile '{prof.name}' v{prof.version} ({prof.currency})",
        f"contingency applied at {prof.contingency_rate:.0%}",
        "prototype-level estimate; excludes financing, O&M, taxes and "
        "detailed engineering",
    )
    return res
