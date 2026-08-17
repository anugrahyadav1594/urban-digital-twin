"""Ranking and the end-to-end suitability pipeline. ARCHITECTURE §14."""
from __future__ import annotations

from typing import Any, Sequence

from ..contracts import EngineResult, Provenance
from .candidates import Candidate, generate_candidates
from .filters import SiteRequirements, hard_filter
from .mcda import DEFAULT_PROFILES, ScoringProfile, score_candidates

ALGORITHM = "planning.site_suitability"
ALGORITHM_VERSION = "0.1.0"


def rank_candidates(
    candidates: Sequence[Candidate],
    profile: ScoringProfile,
) -> list[dict[str, Any]]:
    """Score and order candidates. Ties break on candidate id for determinism."""
    if not candidates:
        return []
    scored = score_candidates(
        [c.metrics for c in candidates],
        profile,
        penalties=[c.soft_penalty for c in candidates],
    )
    rows = []
    for c, s in zip(candidates, scored):
        row = c.to_dict()
        row.update({
            "score": s["score"],
            "raw_score": s["raw_score"],
            "penalty": s["penalty"],
            "criteria": s["criteria"],
        })
        rows.append(row)
    rows.sort(key=lambda r: (-r["score"], r["candidate_id"]))
    for i, r in enumerate(rows, start=1):
        r["rank"] = i
    return rows


def site_suitability(
    parcels: Sequence[Any],
    requirements: SiteRequirements,
    provenance: Provenance,
    constraints: Sequence[Any] = (),
    population_zones: Sequence[Any] = (),
    existing_facilities: Sequence[Any] = (),
    graph: Any = None,
    profile: ScoringProfile | None = None,
    service_radius: float = 2000.0,
    top_n: int = 10,
) -> EngineResult:
    """Full pipeline: all parcels -> hard filter -> candidates -> score -> rank.

    ARCHITECTURE §14.2. Rejected parcels are reported with their reasons.
    """
    profile = profile or DEFAULT_PROFILES.get(
        requirements.facility_type, DEFAULT_PROFILES["hospital"]
    )
    res = EngineResult(result_type="site_suitability", provenance=provenance)

    survivors, reports = hard_filter(parcels, requirements, constraints)
    rejected = [r.to_dict() for r in reports if not r.passed]
    penalties = {r.entity_id: r.soft_penalty for r in reports if r.passed}

    if not survivors:
        res.add("parcels_evaluated", len(parcels), "count")
        res.add("candidates_generated", 0, "count")
        res.warnings.append(
            "no parcel satisfied the hard constraints; relax requirements or "
            "widen the search extent"
        )
        res.records = []
        res.artifacts.append({"type": "rejections", "count": str(len(rejected))})
        return res

    candidates = generate_candidates(
        survivors,
        population_zones=population_zones,
        existing_facilities=existing_facilities,
        facility_type=requirements.facility_type,
        service_radius=service_radius,
        penalties=penalties,
        graph=graph,
    )

    if requirements.min_distance_same_type is not None:
        keep = []
        for c in candidates:
            d = c.metrics.get("distance_to_same_type")
            if d is not None and d < requirements.min_distance_same_type:
                rejected.append({
                    "entity_id": c.parcel_id, "passed": False,
                    "constraints_failed": [{
                        "rule": "min_distance_same_type",
                        "threshold": requirements.min_distance_same_type,
                        "observed": d, "severity": "hard",
                    }],
                })
            else:
                keep.append(c)
        candidates = keep

    ranked = rank_candidates(candidates, profile)

    res.records = ranked[:top_n]
    res.add("parcels_evaluated", len(parcels), "count")
    res.add("parcels_rejected", len(rejected), "count")
    res.add("candidates_generated", len(candidates), "count")
    res.add("candidates_returned", len(res.records), "count")
    if ranked:
        res.add("best_score", ranked[0]["score"], "score")
        res.add("median_score", ranked[len(ranked) // 2]["score"], "score")
    res.artifacts.append({
        "type": "scoring_profile",
        "name": profile.name,
        "version": profile.version,
    })
    return res
