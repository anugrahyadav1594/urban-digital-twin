"""Configurable multi-criteria decision analysis. ARCHITECTURE §14.3.

Scoring is configuration, not code. Criteria, normalisation, weights and the
aggregation function live in a versioned ScoringProfile, so changing planning
priorities never requires a redeploy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Mapping, Sequence

Direction = Literal["benefit", "cost"]
Aggregation = Literal["weighted_sum", "weighted_product", "penalized_sum"]


@dataclass(frozen=True)
class Criterion:
    """One scoring dimension.

    direction: 'benefit' (higher is better) or 'cost' (lower is better).
    """

    name: str
    weight: float
    direction: Direction = "benefit"
    unit: str = ""
    floor: float | None = None    # clamp before normalising
    ceiling: float | None = None


@dataclass(frozen=True)
class ScoringProfile:
    """A named, versioned set of criteria (§14.3, §25)."""

    name: str
    version: str
    criteria: tuple[Criterion, ...]
    aggregation: Aggregation = "weighted_sum"
    normalization: Literal["minmax", "zscore_clipped"] = "minmax"

    def weights(self) -> dict[str, float]:
        return {c.name: c.weight for c in self.criteria}

    def normalized_weights(self) -> dict[str, float]:
        total = sum(abs(c.weight) for c in self.criteria) or 1.0
        return {c.name: c.weight / total for c in self.criteria}

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "aggregation": self.aggregation,
            "normalization": self.normalization,
            "criteria": [
                {"name": c.name, "weight": c.weight, "direction": c.direction,
                 "unit": c.unit}
                for c in self.criteria
            ],
        }


def normalize(
    values: Sequence[float | None],
    direction: Direction = "benefit",
    method: str = "minmax",
    floor: float | None = None,
    ceiling: float | None = None,
) -> list[float]:
    """Scale raw metric values to 0..1. Missing values score 0.0.

    A degenerate range (all equal) yields 0.5 for every present value —
    a flat criterion must not arbitrarily favour any candidate.
    """
    clean = [v for v in values if v is not None]
    if not clean:
        return [0.0] * len(values)

    lo = floor if floor is not None else min(clean)
    hi = ceiling if ceiling is not None else max(clean)

    if method == "zscore_clipped":
        n = len(clean)
        mean = sum(clean) / n
        var = sum((v - mean) ** 2 for v in clean) / n
        sd = var ** 0.5
        if sd == 0:
            return [0.5 if v is not None else 0.0 for v in values]
        out = []
        for v in values:
            if v is None:
                out.append(0.0)
                continue
            z = max(-3.0, min(3.0, (v - mean) / sd))
            s = (z + 3.0) / 6.0
            out.append(1.0 - s if direction == "cost" else s)
        return out

    if hi == lo:
        return [0.5 if v is not None else 0.0 for v in values]

    out = []
    for v in values:
        if v is None:
            out.append(0.0)
            continue
        s = (min(max(v, lo), hi) - lo) / (hi - lo)
        out.append(1.0 - s if direction == "cost" else s)
    return out


def score_candidates(
    raw_metrics: Sequence[Mapping[str, float | None]],
    profile: ScoringProfile,
    penalties: Sequence[float] | None = None,
) -> list[dict[str, Any]]:
    """Score every candidate under the profile.

    Returns per-candidate dicts holding the raw value, normalised value,
    weight and weighted contribution for each criterion (§14.4).
    """
    n = len(raw_metrics)
    if n == 0:
        return []
    penalties = list(penalties or [0.0] * n)
    weights = profile.normalized_weights()

    normed: dict[str, list[float]] = {}
    for c in profile.criteria:
        col = [m.get(c.name) for m in raw_metrics]
        normed[c.name] = normalize(
            col, c.direction, profile.normalization, c.floor, c.ceiling
        )

    results: list[dict[str, Any]] = []
    for i in range(n):
        breakdown: dict[str, Any] = {}
        for c in profile.criteria:
            w = weights[c.name]
            nv = normed[c.name][i]
            breakdown[c.name] = {
                "raw": raw_metrics[i].get(c.name),
                "unit": c.unit,
                "normalized": round(nv, 6),
                "weight": round(w, 6),
                "contribution": round(nv * w, 6),
                "direction": c.direction,
            }

        if profile.aggregation == "weighted_sum":
            total = sum(b["contribution"] for b in breakdown.values())
        elif profile.aggregation == "weighted_product":
            total = 1.0
            for c in profile.criteria:
                total *= max(normed[c.name][i], 1e-6) ** weights[c.name]
        elif profile.aggregation == "penalized_sum":
            total = sum(b["contribution"] for b in breakdown.values()) - penalties[i]
        else:
            raise ValueError(f"unknown aggregation: {profile.aggregation}")

        if profile.aggregation != "penalized_sum":
            total -= penalties[i]

        results.append({
            "score": round(max(0.0, min(1.0, total)), 6),
            "raw_score": round(total, 6),
            "penalty": round(penalties[i], 6),
            "criteria": breakdown,
        })
    return results


# Default profiles. Real deployments load these from configuration.
DEFAULT_PROFILES: dict[str, ScoringProfile] = {
    "hospital": ScoringProfile(
        name="hospital", version="0.1.0",
        criteria=(
            Criterion("population_served", 0.35, "benefit", "persons"),
            Criterion("travel_time_mean", 0.25, "cost", "seconds"),
            Criterion("distance_to_same_type", 0.15, "benefit", "m"),
            Criterion("flood_risk", 0.15, "cost", "index"),
            Criterion("slope", 0.10, "cost", "degrees"),
        ),
    ),
    "school": ScoringProfile(
        name="school", version="0.1.0",
        criteria=(
            Criterion("population_served", 0.40, "benefit", "persons"),
            Criterion("travel_time_mean", 0.30, "cost", "seconds"),
            Criterion("distance_to_same_type", 0.20, "benefit", "m"),
            Criterion("flood_risk", 0.10, "cost", "index"),
        ),
    ),
    "fire_station": ScoringProfile(
        name="fire_station", version="0.1.0",
        criteria=(
            Criterion("travel_time_mean", 0.45, "cost", "seconds"),
            Criterion("population_served", 0.30, "benefit", "persons"),
            Criterion("distance_to_same_type", 0.15, "benefit", "m"),
            Criterion("flood_risk", 0.10, "cost", "index"),
        ),
    ),
}
