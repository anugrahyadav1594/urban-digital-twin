"""Development package generation. Product report §1.

The core product idea from the report:

    "Do not recommend buildings independently. Recommend the ecosystem
     required to make each intervention actually useful. A hospital without
     access, for example, should be treated as an incomplete solution."

So this engine never emits a bare facility. Every primary intervention pulls
in its dependencies — access road, connectivity, drainage — as explicit child
actions, and the cost and uplift of the whole bundle are reported together.

Siting reuses the existing candidate generator and MCDA ranking rather than
inventing a second placement algorithm.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence

from ..contracts import EngineResult, Provenance
from ..cost.estimator import DEFAULT_COST_PROFILE, CostProfile
from .dimensions import DIMENSIONS, dimension_by_key

ALGORITHM = "development_package"
ALGORITHM_VERSION = "1.0.0"


@dataclass
class Action:
    """One recommended intervention."""

    id: str
    kind: str                    # facility | road | open_space | utility
    label: str
    dimension: str               # which dimension it improves
    rationale: str
    cost: float = 0.0
    currency: str = "INR"
    population_served: float = 0.0
    expected_uplift: float = 0.0        # points on the overall score
    priority: int = 0
    depends_on: list[str] = field(default_factory=list)
    location: dict[str, float] | None = None
    parent_id: str | None = None        # set on dependency actions
    feasibility: str = "medium"
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "label": self.label,
            "dimension": self.dimension,
            "rationale": self.rationale,
            "cost": round(self.cost),
            "currency": self.currency,
            "populationServed": round(self.population_served),
            "expectedUplift": round(self.expected_uplift, 2),
            "priority": self.priority,
            "dependsOn": self.depends_on,
            "location": self.location,
            "parentId": self.parent_id,
            "feasibility": self.feasibility,
            "detail": self.detail,
        }


# What each facility type needs in order to actually function (report §1).
# kind, label template, cost key, quantity basis.
DEPENDENCIES: dict[str, tuple[tuple[str, str, str], ...]] = {
    "hospital": (
        ("road", "Access road to {label}", "road_per_m_collector"),
        ("utility", "Drainage and services for {label}", "drainage_per_m"),
    ),
    "clinic": (
        ("road", "Access road to {label}", "road_per_m_local"),
    ),
    "school": (
        ("road", "Access road to {label}", "road_per_m_local"),
        ("utility", "Drainage and services for {label}", "drainage_per_m"),
    ),
    "fire_station": (
        ("road", "Priority emergency access to {label}", "road_per_m_arterial"),
    ),
    "park": (
        ("road", "Pedestrian access to {label}", "road_per_m_local"),
    ),
    "recreation": (
        ("road", "Access road to {label}", "road_per_m_local"),
    ),
}

# Default access-road length assumed per new facility, in metres. A real
# alignment comes from the road-design engine once a site is confirmed; this
# is the planning-stage allowance and is stated as an assumption.
ACCESS_ROAD_M = 250.0

# Which facility type addresses which weak dimension.
REMEDY: dict[str, tuple[str, ...]] = {
    "healthcare": ("hospital", "clinic"),
    "education": ("school",),
    "recreation": ("recreation",),
    "green_space": ("park",),
    "resilience": ("fire_station",),
    "facility_access": ("clinic", "school"),
    "mobility": (),          # handled by road actions, not facilities
    "infrastructure": (),
    "landuse": (),
    "constraints": (),
}

FACILITY_COST: dict[str, tuple[str, float]] = {
    # type -> (cost rate key, quantity)
    "hospital": ("hospital_per_bed", 100.0),
    "clinic": ("hospital_per_bed", 12.0),
    "school": ("school_per_seat", 600.0),
    "fire_station": ("fire_station_fixed", 1.0),
    "park": ("site_preparation_per_m2", 8000.0),
    "recreation": ("site_preparation_per_m2", 3000.0),
}

FACILITY_LABEL: dict[str, str] = {
    "hospital": "Hospital",
    "clinic": "Primary health clinic",
    "school": "School",
    "fire_station": "Fire station",
    "park": "Neighbourhood park",
    "recreation": "Community recreation centre",
}


def _facility_cost(ftype: str, profile: CostProfile) -> float:
    key, qty = FACILITY_COST.get(ftype, ("site_preparation_per_m2", 2000.0))
    rate = profile.rate(key) or 0.0
    return rate * qty


def _uplift_for(dim_key: str, current: float | None, dims_weight_total: float,
                weight: float, step: float) -> float:
    """Points added to the overall score by closing part of a gap.

    A dimension contributes weight/total of the overall score, so lifting it
    by `step` points lifts the overall by step * weight / total.
    """
    if dims_weight_total <= 0:
        return 0.0
    return step * (weight / dims_weight_total)


def generate_package(
    *,
    region: str,
    scorecard: dict[str, Any],
    provenance: Provenance,
    parcels: Sequence[Any] = (),
    population_zones: Sequence[Any] = (),
    facilities: Sequence[Any] = (),
    graph: Any | None = None,
    target_uplift: float = 10.0,
    priorities: Sequence[str] = (),
    budget: float | None = None,
    cost_profile: CostProfile | None = None,
    max_actions: int = 12,
) -> EngineResult:
    """Turn a scorecard's gaps into a prioritised, dependency-aware package.

    `priorities` restricts which dimensions may be addressed; empty means
    "let the gap analysis decide".
    """
    profile = cost_profile or DEFAULT_COST_PROFILE
    res = EngineResult(result_type="development_package", provenance=provenance)

    dims = {d["key"]: d for d in scorecard.get("dimensions", [])}
    weight_total = sum(float(d.get("weight", 1.0)) for d in dims.values()
                       if d.get("score") is not None) or 1.0

    # ---- gap analysis (report §1 "identify weak dimensions") -------------
    gaps: list[tuple[str, float, float]] = []   # key, gap points, weight
    for key, d in dims.items():
        score = d.get("score")
        if score is None:
            continue
        bench = d.get("benchmarkScore")
        # Gap against the benchmark when we have one, else against a full
        # 100. Benchmarks are the report's stated yardstick.
        ceiling = bench if bench is not None else 100.0
        gap = max(0.0, float(ceiling) - float(score))
        if gap <= 0.5:
            continue
        if priorities and key not in priorities:
            continue
        gaps.append((key, gap, float(d.get("weight", 1.0))))

    # Biggest weighted gap first: that is where a rupee buys the most score.
    gaps.sort(key=lambda t: t[1] * t[2], reverse=True)

    if not gaps:
        res.warnings.append(
            "No measurable gaps against the benchmark for the selected "
            "priorities; nothing to recommend.")
        res.add("actions", 0, "count")
        res.add("total_cost", 0.0, profile.currency)
        res.add("expected_uplift", 0.0, "points")
        return res

    population = float(scorecard.get("population") or 0.0)
    actions: list[Action] = []
    seq = 0
    cumulative_uplift = 0.0
    cumulative_cost = 0.0

    for key, gap, weight in gaps:
        if cumulative_uplift >= target_uplift or len(actions) >= max_actions:
            break
        dim = dimension_by_key(key)
        if dim is None:
            continue

        remedies = REMEDY.get(key, ())
        if not remedies:
            # Dimensions fixed by network work rather than buildings.
            if key in ("mobility", "infrastructure"):
                seq += 1
                aid = f"act-{seq:02d}"
                length_m = 1200.0
                rate = profile.rate("road_per_m_collector") or 0.0
                cost = rate * length_m
                step = min(gap, 12.0)
                uplift = _uplift_for(key, dims[key].get("score"),
                                     weight_total, weight, step)
                if budget is not None and cumulative_cost + cost > budget:
                    continue
                actions.append(Action(
                    id=aid, kind="road",
                    label=f"New collector road corridor ({length_m:.0f} m)",
                    dimension=key,
                    rationale=(f"{dim.label} scores {dims[key].get('score')} "
                               f"against a benchmark of "
                               f"{dims[key].get('benchmarkScore')}. Additional "
                               f"network length raises connectivity and "
                               f"shortens journeys."),
                    cost=cost, currency=profile.currency,
                    population_served=population * 0.15,
                    expected_uplift=uplift, priority=len(actions) + 1,
                    feasibility="medium",
                    detail={"lengthM": length_m, "roadClass": "collector"},
                ))
                cumulative_cost += cost
                cumulative_uplift += uplift
            continue

        # One facility per remedy type, best-sited first.
        for ftype in remedies:
            if cumulative_uplift >= target_uplift or len(actions) >= max_actions:
                break
            seq += 1
            aid = f"act-{seq:02d}"
            label = FACILITY_LABEL.get(ftype, ftype.replace("_", " ").title())
            cost = _facility_cost(ftype, profile)

            site = _best_site(parcels, population_zones, facilities, ftype,
                              graph)
            served = site.get("populationServed", 0.0) if site else 0.0

            step = min(gap, 15.0)
            uplift = _uplift_for(key, dims[key].get("score"), weight_total,
                                 weight, step)

            deps = DEPENDENCIES.get(ftype, ())
            dep_cost = 0.0
            for _kind, _tmpl, rate_key in deps:
                dep_cost += (profile.rate(rate_key) or 0.0) * ACCESS_ROAD_M

            if budget is not None and cumulative_cost + cost + dep_cost > budget:
                res.warnings.append(
                    f"{label} omitted: would exceed the budget.")
                continue

            primary = Action(
                id=aid, kind="facility", label=label, dimension=key,
                rationale=(
                    f"{dim.label} scores "
                    f"{dims[key].get('score')} / 100 against a benchmark of "
                    f"{dims[key].get('benchmarkScore')}. "
                    + (f"Best available site serves "
                       f"{served:,.0f} residents."
                       if served else
                       "Sited on the highest-scoring vacant parcel.")),
                cost=cost, currency=profile.currency,
                population_served=served,
                expected_uplift=uplift, priority=len(actions) + 1,
                location=(site or {}).get("location"),
                feasibility=(site or {}).get("feasibility", "medium"),
                detail={"facilityType": ftype,
                        **{k: v for k, v in (site or {}).items()
                           if k not in ("location", "feasibility")}},
            )
            actions.append(primary)
            cumulative_cost += cost
            cumulative_uplift += uplift

            # Dependencies: the ecosystem that makes the facility usable.
            for kind, tmpl, rate_key in deps:
                seq += 1
                did = f"act-{seq:02d}"
                dcost = (profile.rate(rate_key) or 0.0) * ACCESS_ROAD_M
                actions.append(Action(
                    id=did, kind=kind,
                    label=tmpl.format(label=label),
                    dimension=key,
                    rationale=(f"{label} is not usable without this. "
                               f"Recommended as part of the same package."),
                    cost=dcost, currency=profile.currency,
                    population_served=0.0,
                    expected_uplift=0.0,
                    priority=len(actions) + 1,
                    parent_id=aid,
                    feasibility="high",
                    detail={"lengthM": ACCESS_ROAD_M},
                ))
                cumulative_cost += dcost
                primary.depends_on.append(did)

    # Contingency, consistent with the cost engine's own convention.
    contingency = cumulative_cost * profile.contingency_rate
    total_cost = cumulative_cost + contingency

    res.add("actions", len(actions), "count")
    res.add("primary_actions",
            sum(1 for a in actions if a.parent_id is None), "count")
    res.add("total_cost", round(total_cost), profile.currency)
    res.add("base_cost", round(cumulative_cost), profile.currency)
    res.add("contingency", round(contingency), profile.currency)
    res.add("expected_uplift", round(cumulative_uplift, 2), "points")
    res.add("target_uplift", target_uplift, "points")
    res.add("projected_score",
            round((scorecard.get("overallScore") or 0.0) + cumulative_uplift, 1),
            "points")

    if cumulative_uplift < target_uplift:
        res.warnings.append(
            f"Reached +{cumulative_uplift:.1f} points of the requested "
            f"+{target_uplift:.1f}. "
            + ("Budget exhausted." if budget is not None
               else "No further high-impact interventions available within "
                    "the action limit."))

    res.records = [a.to_dict() for a in actions]
    res.provenance = provenance.with_assumptions(
        f"Access road allowance of {ACCESS_ROAD_M:.0f} m per new facility.",
        f"Contingency applied at {profile.contingency_rate:.0%}.",
        "Uplift is a planning-stage projection from gap closure, not a "
        "re-run of the scoring engine.",
    )
    return res


def _best_site(parcels: Sequence[Any], zones: Sequence[Any],
               facilities: Sequence[Any], facility_type: str,
               graph: Any | None) -> dict[str, Any] | None:
    """Pick a site with the existing candidate generator, if data allows."""
    if not parcels:
        return None
    try:
        from ..planning.candidates import generate_candidates
        cands = generate_candidates(
            parcels=parcels,
            population_zones=zones,
            existing_facilities=facilities,
            facility_type=facility_type,
            service_radius=2000.0,
            graph=graph,
        )
        if not cands:
            return None
        best = max(cands,
                   key=lambda c: float(getattr(c, "metrics", {})
                                       .get("population_served", 0.0) or 0.0))
        geom = getattr(best, "geometry", None)
        loc = None
        if geom is not None:
            try:
                p = geom.representative_point()
                loc = {"x": float(p.x), "y": float(p.y)}
            except Exception:                                # noqa: BLE001
                loc = None
        m = dict(getattr(best, "metrics", {}) or {})
        return {
            "location": loc,
            "populationServed": float(m.get("population_served", 0.0) or 0.0),
            "parcelId": str(getattr(best, "id", "") or ""),
            "areaM2": round(float(m.get("area", 0.0) or 0.0)),
            "feasibility": ("high" if float(m.get("flood_risk", 0) or 0) < 0.2
                            else "medium"),
        }
    except Exception:                                        # noqa: BLE001
        return None
        