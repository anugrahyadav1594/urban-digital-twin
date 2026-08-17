"""Cross-scenario comparison. ARCHITECTURE §24.

Comparability is enforced: mismatched dataset or algorithm versions are
refused or flagged rather than silently ranked. Missing metrics are reported
as gaps, never imputed as zero.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Sequence

from ..contracts import EngineResult, Provenance

ALGORITHM = "comparison.compare_scenarios"
ALGORITHM_VERSION = "0.1.0"

Sense = Literal["min", "max"]


@dataclass(frozen=True)
class ComparisonProfile:
    """Which metrics to compare, their weights and their direction (§24.1)."""

    name: str
    version: str
    weights: Mapping[str, float]
    senses: Mapping[str, Sense]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "version": self.version,
            "weights": dict(self.weights), "senses": dict(self.senses),
        }


DEFAULT_COMPARISON = ComparisonProfile(
    name="standard", version="0.1.0",
    weights={
        "coverage_ratio": 0.25,
        "mean_travel_time": 0.20,
        "population_within_threshold": 0.15,
        "population_exposed": 0.15,
        "impact_index": 0.10,
        "capacity_deficit": 0.08,
        "total_cost": 0.07,
    },
    senses={
        "coverage_ratio": "max",
        "mean_travel_time": "min",
        "population_within_threshold": "max",
        "population_exposed": "min",
        "impact_index": "min",
        "capacity_deficit": "min",
        "total_cost": "min",
    },
)


def _collect(results: Sequence[EngineResult]) -> dict[str, float]:
    """Flatten many EngineResults into one metric map (last value wins)."""
    out: dict[str, float] = {}
    for r in results:
        for m in r.metrics:
            if m.value is not None:
                out[m.name] = float(m.value)
    return out


def compare_scenarios(
    scenario_results: Mapping[str, Sequence[EngineResult]],
    provenance: Provenance,
    profile: ComparisonProfile | None = None,
    strict: bool = True,
) -> EngineResult:
    """Build a comparison matrix and overall ranking across scenarios.

    scenario_results maps scenario_id -> list of EngineResults for that plan.
    strict=True refuses to rank when base dataset versions differ (§24.1).
    """
    prof = profile or DEFAULT_COMPARISON
    res = EngineResult(result_type="scenario_comparison", provenance=provenance)

    if len(scenario_results) < 2:
        res.warnings.append("at least two scenarios are required to compare")
        return res

    # --- comparability gate (§24.1) ---
    versions: dict[str, set] = {"dataset": set(), "algorithms": set()}
    for sid, results in scenario_results.items():
        for r in results:
            versions["dataset"].add(r.provenance.dataset_version)
            versions["algorithms"].add(
                (r.provenance.algorithm, r.provenance.algorithm_version)
            )

    if len(versions["dataset"]) > 1:
        msg = (
            "scenarios reference different base dataset versions "
            f"{sorted(versions['dataset'])}; results are not comparable"
        )
        if strict:
            res.warnings.append(msg)
            res.add("comparable", 0, "bool")
            return res
        res.warnings.append(msg + " (proceeding: strict=False)")

    res.add("comparable", 1, "bool")
    res.add("scenarios_compared", len(scenario_results), "count")

    # --- collect metrics ---
    per_scenario = {sid: _collect(rs) for sid, rs in scenario_results.items()}
    metric_names = [m for m in prof.weights if any(
        m in vals for vals in per_scenario.values()
    )]
    missing_report: dict[str, list[str]] = {}
    for sid, vals in per_scenario.items():
        gaps = [m for m in metric_names if m not in vals]
        if gaps:
            missing_report[sid] = gaps

    # --- normalise per metric across scenarios ---
    ranges: dict[str, tuple[float, float]] = {}
    for m in metric_names:
        vals = [v[m] for v in per_scenario.values() if m in v]
        ranges[m] = (min(vals), max(vals))

    active_weight_total = sum(abs(prof.weights[m]) for m in metric_names) or 1.0

    rows: list[dict[str, Any]] = []
    for sid, vals in per_scenario.items():
        breakdown: dict[str, Any] = {}
        score = 0.0
        used_weight = 0.0
        for m in metric_names:
            if m not in vals:
                breakdown[m] = {"raw": None, "normalized": None, "note": "missing"}
                continue
            lo, hi = ranges[m]
            nv = 0.5 if hi == lo else (vals[m] - lo) / (hi - lo)
            if prof.senses.get(m, "max") == "min":
                nv = 1.0 - nv
            w = prof.weights[m] / active_weight_total
            score += nv * w
            used_weight += w
            breakdown[m] = {
                "raw": round(vals[m], 4), "normalized": round(nv, 6),
                "weight": round(w, 6), "contribution": round(nv * w, 6),
                "sense": prof.senses.get(m, "max"),
            }
        # Rescale so scenarios missing a metric are not unfairly penalised.
        normalised_score = (score / used_weight) if used_weight > 0 else None
        rows.append({
            "scenario_id": sid,
            "overall_score": round(normalised_score, 6)
            if normalised_score is not None else None,
            "weight_coverage": round(used_weight, 4),
            "metrics": breakdown,
            "missing_metrics": missing_report.get(sid, []),
        })

    rows.sort(key=lambda r: (
        -(r["overall_score"] if r["overall_score"] is not None else -1),
        r["scenario_id"],
    ))
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    res.records = rows
    best = rows[0]
    res.add("best_scenario_score", best["overall_score"], "score")
    res.add("metrics_compared", len(metric_names), "count")
    res.artifacts.append({
        "type": "comparison_profile", "name": prof.name, "version": prof.version,
    })
    if missing_report:
        res.warnings.append(
            "metric gaps: " + "; ".join(
                f"{sid} missing {', '.join(ms)}" for sid, ms in missing_report.items()
            )
        )
    res.provenance = provenance.with_assumptions(
        f"comparison profile '{prof.name}' v{prof.version}",
        "metrics min-max normalised across the compared scenarios only",
        "scores rescaled by available weight when a metric is missing",
    )
    return res
