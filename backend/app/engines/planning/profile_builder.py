"""Build a ScoringProfile from planner-supplied weights.

The UI exposes friendly criterion names ("Population", "Flood risk") on 0-100
sliders. The engines use internal metric names on normalised weights. Without
this translation the sliders were accepted by the API and silently discarded,
so every run returned the built-in profile's ranking no matter what the
planner set.

Mapping is explicit and one-way: UI label -> engine metric. Unknown labels are
reported rather than ignored, because a typo that silently drops a criterion
is indistinguishable from the criterion having no effect.
"""
from __future__ import annotations

from typing import Any, Mapping

from .mcda import DEFAULT_PROFILES, Criterion, ScoringProfile

# UI label (lowercased) -> (engine metric, direction, unit)
UI_TO_METRIC: dict[str, tuple[str, str, str]] = {
    "population": ("population_served", "benefit", "persons"),
    "population served": ("population_served", "benefit", "persons"),
    "accessibility": ("travel_time_mean", "cost", "seconds"),
    "travel time": ("travel_time_mean", "cost", "seconds"),
    "land suitability": ("area", "benefit", "m2"),
    "area": ("area", "benefit", "m2"),
    "flood risk": ("flood_risk", "cost", "index"),
    "flood": ("flood_risk", "cost", "index"),
    "existing coverage": ("distance_to_same_type", "benefit", "m"),
    "coverage": ("distance_to_same_type", "benefit", "m"),
    "distance to same type": ("distance_to_same_type", "benefit", "m"),
    "environment": ("slope", "cost", "degrees"),
    "slope": ("slope", "cost", "degrees"),
    "terrain": ("slope", "cost", "degrees"),
}

# Metrics the candidate generator actually produces. A weight on anything
# else would normalise to a column of None and score 0 for every candidate.
SUPPORTED_METRICS = {
    "population_served", "travel_time_mean", "distance_to_same_type",
    "flood_risk", "slope", "area",
}


def build_profile(
    weights: Mapping[str, float] | None,
    facility_type: str = "hospital",
    aggregation: str | None = None,
    normalization: str | None = None,
) -> tuple[ScoringProfile, list[str]]:
    """Return (profile, warnings).

    Falls back to the built-in profile for `facility_type` when no usable
    weights are supplied, so behaviour is unchanged for callers that send
    nothing.
    """
    base = DEFAULT_PROFILES.get(facility_type, DEFAULT_PROFILES["hospital"])
    warnings: list[str] = []

    if not weights:
        return base, warnings

    merged: dict[str, float] = {}
    directions: dict[str, tuple[str, str]] = {}

    for label, raw in weights.items():
        try:
            w = float(raw)
        except (TypeError, ValueError):
            warnings.append(f"weight for '{label}' is not a number; ignored")
            continue
        if w < 0:
            warnings.append(f"negative weight for '{label}' clamped to 0")
            w = 0.0

        key = str(label).strip().lower()
        mapped = UI_TO_METRIC.get(key)
        if mapped is None:
            # Allow raw engine metric names too.
            if key in SUPPORTED_METRICS:
                direction = "cost" if key in (
                    "travel_time_mean", "flood_risk", "slope") else "benefit"
                mapped = (key, direction, "")
            else:
                warnings.append(
                    f"unknown criterion '{label}' ignored; supported: "
                    + ", ".join(sorted(SUPPORTED_METRICS)))
                continue

        metric, direction, unit = mapped
        merged[metric] = merged.get(metric, 0.0) + w
        directions[metric] = (direction, unit)

    positive = {k: v for k, v in merged.items() if v > 0}
    if not positive:
        warnings.append(
            "no usable criterion weights supplied; using the built-in "
            f"'{base.name}' profile")
        return base, warnings

    total = sum(positive.values())
    criteria = tuple(
        Criterion(name=metric, weight=w / total,
                  direction=directions[metric][0],   # type: ignore[arg-type]
                  unit=directions[metric][1])
        for metric, w in sorted(positive.items())
    )

    profile = ScoringProfile(
        name=f"custom:{facility_type}",
        version="user",
        criteria=criteria,
        aggregation=aggregation or base.aggregation,     # type: ignore[arg-type]
        normalization=normalization or base.normalization,  # type: ignore[arg-type]
    )
    return profile, warnings


def describe_criteria() -> list[dict[str, Any]]:
    """Machine-readable catalogue for the UI to render controls from."""
    seen: dict[str, dict[str, Any]] = {}
    for label, (metric, direction, unit) in UI_TO_METRIC.items():
        entry = seen.setdefault(metric, {
            "metric": metric, "direction": direction, "unit": unit,
            "labels": [],
        })
        entry["labels"].append(label)
    for e in seen.values():
        e["labels"] = sorted(e["labels"])
    return sorted(seen.values(), key=lambda e: e["metric"])
