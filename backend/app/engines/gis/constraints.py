"""Hard/soft constraint evaluation. ARCHITECTURE §12, §14.2.

Exclusions are never silent: every failure records the rule, the threshold and
the observed value (§14.4).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from shapely.strtree import STRtree


@dataclass
class ConstraintReport:
    """Per-entity verdict with full reasoning."""

    entity_id: str
    passed: bool = True
    failed: list[dict[str, Any]] = field(default_factory=list)
    satisfied: list[dict[str, Any]] = field(default_factory=list)
    soft_penalty: float = 0.0

    def fail(self, rule: str, threshold: Any, observed: Any, severity: str = "hard") -> None:
        self.failed.append({
            "rule": rule, "threshold": threshold,
            "observed": observed, "severity": severity,
        })
        if severity == "hard":
            self.passed = False

    def ok(self, rule: str, threshold: Any, observed: Any) -> None:
        self.satisfied.append({
            "rule": rule, "threshold": threshold, "observed": observed,
        })

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "passed": self.passed,
            "constraints_failed": self.failed,
            "constraints_passed": self.satisfied,
            "soft_penalty": round(self.soft_penalty, 6),
        }


def evaluate_constraints(
    parcel: Any,
    constraints: Sequence[Any],
    *,
    min_area: float | None = None,
    max_slope: float | None = None,
    max_flood_risk: float | None = None,
    allowed_zoning: Sequence[str] | None = None,
    allowed_status: Sequence[str] | None = None,
) -> ConstraintReport:
    """Evaluate one parcel against attribute rules and spatial constraints."""
    rep = ConstraintReport(entity_id=str(parcel.id))
    geom = parcel.geometry
    area = float(parcel.area if parcel.area is not None else geom.area)

    if min_area is not None:
        (rep.ok if area >= min_area else rep.fail)("min_area", min_area, round(area, 2))

    if max_slope is not None and parcel.slope is not None:
        s = float(parcel.slope)
        (rep.ok if s <= max_slope else rep.fail)("max_slope", max_slope, s)

    if max_flood_risk is not None and parcel.flood_risk is not None:
        fr = float(parcel.flood_risk)
        (rep.ok if fr <= max_flood_risk else rep.fail)("max_flood_risk", max_flood_risk, fr)

    if allowed_zoning:
        z = parcel.zoning
        (rep.ok if z in allowed_zoning else rep.fail)("allowed_zoning", list(allowed_zoning), z)

    if allowed_status:
        st = parcel.development_status
        (rep.ok if st in allowed_status else rep.fail)(
            "allowed_development_status", list(allowed_status), st
        )

    if constraints:
        geoms = [c.geometry.buffer(c.buffer) if c.buffer else c.geometry
                 for c in constraints]
        tree = STRtree(geoms)
        for i in tree.query(geom):
            c = constraints[int(i)]
            cg = geoms[int(i)]
            if not geom.intersects(cg):
                continue
            overlap = geom.intersection(cg).area / area if area > 0 else 0.0
            if c.severity == "hard":
                rep.fail(f"constraint:{c.type}", "no overlap",
                         round(overlap, 4), severity="hard")
            else:
                rep.soft_penalty += float(c.weight) * overlap
                rep.failed.append({
                    "rule": f"constraint:{c.type}", "threshold": "prefer no overlap",
                    "observed": round(overlap, 4), "severity": "soft",
                })
    return rep


def filter_by_constraints(
    parcels: Sequence[Any], constraints: Sequence[Any], **rules: Any
) -> tuple[list[Any], list[ConstraintReport]]:
    """Split parcels into survivors and a full report list (§14.2)."""
    reports = [evaluate_constraints(p, constraints, **rules) for p in parcels]
    survivors = [p for p, r in zip(parcels, reports) if r.passed]
    return survivors, reports
