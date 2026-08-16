"""Multi-objective optimization helpers. ARCHITECTURE §15."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..contracts import EngineResult, Provenance

ALGORITHM = "optimization.multi_objective"
ALGORITHM_VERSION = "0.1.0"


def _dominates(
    a: Mapping[str, float], b: Mapping[str, float], senses: Mapping[str, str]
) -> bool:
    """True if a is at least as good as b everywhere and strictly better once."""
    better_somewhere = False
    for k, sense in senses.items():
        av, bv = a.get(k), b.get(k)
        if av is None or bv is None:
            continue
        if sense == "min":
            if av > bv:
                return False
            if av < bv:
                better_somewhere = True
        else:
            if av < bv:
                return False
            if av > bv:
                better_somewhere = True
    return better_somewhere


def pareto_front(
    solutions: Sequence[Mapping[str, Any]],
    senses: Mapping[str, str],
    provenance: Provenance | None = None,
) -> list[dict[str, Any]]:
    """Non-dominated subset. senses maps objective name -> 'min' | 'max'."""
    front: list[dict[str, Any]] = []
    for i, s in enumerate(solutions):
        dominated = any(
            _dominates(o, s, senses) for j, o in enumerate(solutions) if i != j
        )
        if not dominated:
            row = dict(s)
            row["pareto_optimal"] = True
            front.append(row)
    return front


def weighted_scalarization(
    solutions: Sequence[Mapping[str, Any]],
    weights: Mapping[str, float],
    senses: Mapping[str, str],
    provenance: Provenance,
) -> EngineResult:
    """Collapse objectives to one score after min-max normalising each."""
    res = EngineResult(result_type="multi_objective", provenance=provenance)
    if not solutions:
        res.warnings.append("no solutions supplied")
        return res

    keys = [k for k in weights if any(k in s for s in solutions)]
    ranges: dict[str, tuple[float, float]] = {}
    for k in keys:
        vals = [float(s[k]) for s in solutions if s.get(k) is not None]
        ranges[k] = (min(vals), max(vals)) if vals else (0.0, 0.0)

    wsum = sum(abs(w) for w in weights.values()) or 1.0
    rows = []
    for s in solutions:
        total = 0.0
        parts = {}
        for k in keys:
            v = s.get(k)
            if v is None:
                continue
            lo, hi = ranges[k]
            nv = 0.5 if hi == lo else (float(v) - lo) / (hi - lo)
            if senses.get(k, "max") == "min":
                nv = 1.0 - nv
            w = weights[k] / wsum
            parts[k] = {"raw": v, "normalized": round(nv, 6),
                        "weight": round(w, 6), "contribution": round(nv * w, 6)}
            total += nv * w
        rows.append({**dict(s), "score": round(total, 6), "objectives": parts})

    rows.sort(key=lambda r: -r["score"])
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    front_ids = {id(x) for x in pareto_front(solutions, senses)}
    res.records = rows
    res.add("solutions_evaluated", len(rows), "count")
    res.add("best_score", rows[0]["score"], "score")
    res.add("pareto_optimal_count", len(pareto_front(solutions, senses)), "count")
    return res
