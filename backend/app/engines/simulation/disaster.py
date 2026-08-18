"""Disaster scenario simulation with mitigation measures. ARCHITECTURE §17.

Models a hazard event, what it exposes, how it degrades the road network, and
how well emergency services still cover the city under those conditions — then
re-runs the same event with mitigation measures active so the two can be
compared.

Scope, stated honestly: hazard footprints here are parametric (radius and
intensity decay), not solver output. A real flood depth grid or fire spread
model belongs behind the §17.2 adapters. What this engine does correctly is
propagate a hazard extent through exposure, network degradation and response
coverage in one consistent pass, which is what makes the measures comparable.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from ..contracts import EngineResult, Provenance

ALGORITHM = "simulation.disaster"
ALGORITHM_VERSION = "0.1.0"

# Hazard behaviour per type. `road_block_ratio` is the fraction of the hazard
# radius within which roads are treated as impassable; fires close streets
# tight to the fire ground, floods close everything they touch.
HAZARD_TYPES: dict[str, dict[str, Any]] = {
    "fire": {
        "label": "Urban fire",
        "road_block_ratio": 0.55,
        "road_slow_ratio": 1.0,
        "spreads_with_buildings": True,
        "default_radius_m": 400.0,
        "unit": "fire appliances",
        "responder_type": "fire_station",
    },
    "flood": {
        "label": "Flood",
        "road_block_ratio": 1.0,
        "road_slow_ratio": 1.4,
        "spreads_with_buildings": False,
        "default_radius_m": 900.0,
        "unit": "rescue boats",
        "responder_type": "fire_station",
    },
    "earthquake": {
        "label": "Earthquake",
        "road_block_ratio": 0.35,
        "road_slow_ratio": 1.8,
        "spreads_with_buildings": False,
        "default_radius_m": 1500.0,
        "unit": "USAR teams",
        "responder_type": "hospital",
    },
    "chemical": {
        "label": "Chemical release",
        "road_block_ratio": 0.9,
        "road_slow_ratio": 1.5,
        "spreads_with_buildings": False,
        "default_radius_m": 700.0,
        "unit": "hazmat units",
        "responder_type": "fire_station",
    },
}

# Mitigation measures. `reduces` names the quantity each measure acts on, so a
# measure can never silently improve a number it has no mechanism to affect.
MEASURES: dict[str, dict[str, Any]] = {
    "early_warning": {
        "label": "Early warning system",
        "reduces": "population_exposed",
        "factor": 0.45,
        "note": "evacuation before impact; does not reduce physical damage",
    },
    "flood_barrier": {
        "label": "Flood barriers",
        "reduces": "hazard_radius",
        "factor": 0.70,
        "applies_to": ("flood",),
        "note": "contains the inundation extent",
    },
    "fire_break": {
        "label": "Fire breaks / setbacks",
        "reduces": "hazard_radius",
        "factor": 0.75,
        "applies_to": ("fire",),
        "note": "limits spread across the block",
    },
    "building_retrofit": {
        "label": "Structural retrofit",
        "reduces": "buildings_damaged",
        "factor": 0.55,
        "note": "reduces collapse and severe damage counts",
    },
    "road_redundancy": {
        "label": "Redundant road links",
        "reduces": "roads_blocked",
        "factor": 0.60,
        "note": "keeps alternative approaches open for responders",
    },
    "backup_power": {
        "label": "Backup power at facilities",
        "reduces": "facilities_offline",
        "factor": 0.25,
        "note": "keeps critical facilities operational",
    },
}


@dataclass
class Hazard:
    """A parametric hazard footprint."""

    type: str
    center: Any                      # shapely Point, ANALYSIS CRS (metres)
    radius_m: float
    intensity: float = 1.0           # 0..1 at the centre
    geometry: Any = None
    measures: tuple[str, ...] = ()
    notes: list[str] = field(default_factory=list)

    def footprint(self):
        if self.geometry is not None:
            return self.geometry
        return self.center.buffer(max(self.radius_m, 1.0))

    def core(self, ratio: float):
        """Inner zone where the hazard is severe enough to close roads."""
        return self.center.buffer(max(self.radius_m * ratio, 1.0))

    def severity_at(self, geom: Any) -> float:
        """Linear decay from the centre; 0 outside the footprint."""
        d = self.center.distance(geom)
        if d >= self.radius_m:
            return 0.0
        return float(self.intensity) * (1.0 - d / self.radius_m)


def build_hazard(
    hazard_type: str,
    center: Any,
    radius_m: float | None = None,
    intensity: float = 1.0,
    measures: Iterable[str] = (),
) -> Hazard:
    """Construct a hazard, applying any extent-reducing measures."""
    spec = HAZARD_TYPES.get(hazard_type, HAZARD_TYPES["fire"])
    r = float(radius_m or spec["default_radius_m"])
    active = tuple(m for m in measures if m in MEASURES)
    notes: list[str] = []

    for m in active:
        md = MEASURES[m]
        if md["reduces"] != "hazard_radius":
            continue
        applies = md.get("applies_to")
        if applies and hazard_type not in applies:
            notes.append(
                f"{md['label']} has no effect on a {hazard_type} event; ignored")
            continue
        r *= md["factor"]
        notes.append(f"{md['label']} reduced the extent to {r:.0f} m")

    h = Hazard(type=hazard_type, center=center, radius_m=r,
               intensity=max(0.0, min(float(intensity), 1.0)),
               measures=active)
    h.notes = notes
    return h


def _measure_factor(measures: Sequence[str], quantity: str,
                    hazard_type: str) -> float:
    """Combined multiplier applied to `quantity`. 1.0 means no measure acts."""
    f = 1.0
    for m in measures:
        md = MEASURES.get(m)
        if not md or md["reduces"] != quantity:
            continue
        applies = md.get("applies_to")
        if applies and hazard_type not in applies:
            continue
        f *= md["factor"]
    return f


def simulate_disaster(
    hazard: Hazard,
    provenance: Provenance,
    buildings: Sequence[Any] = (),
    population_zones: Sequence[Any] = (),
    facilities: Sequence[Any] = (),
    roads: Sequence[Any] = (),
) -> EngineResult:
    """Exposure and damage for one hazard, with measures already applied."""
    from shapely.strtree import STRtree

    spec = HAZARD_TYPES.get(hazard.type, HAZARD_TYPES["fire"])
    res = EngineResult(result_type="disaster_simulation", provenance=provenance)
    fp = hazard.footprint()
    core = hazard.core(spec["road_block_ratio"])

    # ---- buildings -------------------------------------------------------
    hit: list[dict[str, Any]] = []
    if buildings:
        geoms = [b.geometry for b in buildings]
        tree = STRtree(geoms)
        for idx in tree.query(fp):                       # integer indices
            b = buildings[int(idx)]
            if not fp.intersects(b.geometry):
                continue
            sev = hazard.severity_at(b.geometry.centroid)
            if sev <= 0:
                continue
            hit.append({
                "entity_id": str(getattr(b, "id", idx)),
                "kind": "building",
                "severity": round(sev, 3),
                "damage_state": ("severe" if sev > 0.66
                                 else "moderate" if sev > 0.33 else "light"),
                "population_estimate": float(
                    getattr(b, "population_estimate", 0.0) or 0.0),
            })

    retro = _measure_factor(hazard.measures, "buildings_damaged", hazard.type)
    severe = sum(1 for r in hit if r["damage_state"] == "severe")
    severe_mitigated = int(round(severe * retro))

    # ---- population ------------------------------------------------------
    pop_exposed = 0.0
    if population_zones:
        from ..gis.aggregation import population_within
        pop_exposed, _ = population_within(fp, population_zones)
    elif hit:
        pop_exposed = sum(r["population_estimate"] for r in hit)

    warn_f = _measure_factor(hazard.measures, "population_exposed", hazard.type)
    pop_at_risk = pop_exposed * warn_f

    # ---- facilities ------------------------------------------------------
    fac_hit: list[dict[str, Any]] = []
    for f in facilities:
        g = getattr(f, "geometry", None)
        if g is None or not fp.intersects(g):
            continue
        sev = hazard.severity_at(g)
        if sev <= 0:
            continue
        fac_hit.append({
            "entity_id": str(getattr(f, "id", "")),
            "kind": "facility",
            "name": getattr(f, "name", None),
            "facility_type": getattr(f, "type", None),
            "severity": round(sev, 3),
        })
    power = _measure_factor(hazard.measures, "facilities_offline", hazard.type)
    offline = int(round(len(fac_hit) * power))

    # ---- roads -----------------------------------------------------------
    blocked_ids: list[str] = []
    slowed_ids: list[str] = []
    for r in roads:
        g = getattr(r, "geometry", None)
        if g is None or not fp.intersects(g):
            continue
        (blocked_ids if core.intersects(g) else slowed_ids).append(
            str(getattr(r, "id", "")))

    redundancy = _measure_factor(hazard.measures, "roads_blocked", hazard.type)
    if redundancy < 1.0 and blocked_ids:
            keep = int(round(len(blocked_ids) * redundancy))       # Deterministic: keep the lowest ids blocked, reopen the rest.
            blocked_ids = sorted(blocked_ids)[:keep]

    res.records = hit[:200] + fac_hit
    res.add("hazard_radius_m", round(hazard.radius_m, 1), "m")
    res.add("hazard_area_km2", round(fp.area / 1e6, 4), "km2")
    res.add("buildings_affected", len(hit), "count")
    res.add("buildings_severe", severe_mitigated, "count")
    res.add("population_exposed", round(pop_exposed, 1), "persons")
    res.add("population_at_risk", round(pop_at_risk, 1), "persons")
    res.add("facilities_affected", len(fac_hit), "count")
    res.add("facilities_offline", offline, "count")
    res.add("roads_blocked", len(blocked_ids), "count")
    res.add("roads_slowed", len(slowed_ids), "count")

    res.artifacts.append({
        "type": "hazard",
        "hazard_type": hazard.type,
        "label": spec["label"],
        "blocked_road_ids": ",".join(blocked_ids[:500]),
        "slowed_road_ids": ",".join(slowed_ids[:500]),
    })
    for n in hazard.notes:
        res.warnings.append(n)
    if not buildings and not population_zones:
        res.warnings.append(
            "no buildings or population zones supplied; exposure is structural "
            "only and understates the human impact")
    return res


def compare_measures(
    baseline: EngineResult,
    mitigated: EngineResult,
    provenance: Provenance,
) -> EngineResult:
    """Quantify what the measures bought, metric by metric."""
    res = EngineResult(result_type="disaster_mitigation_comparison",
                       provenance=provenance)
    b = {m.name: m.value for m in baseline.metrics}
    a = {m.name: m.value for m in mitigated.metrics}

    rows: list[dict[str, Any]] = []
    for key in ("population_at_risk", "buildings_severe", "facilities_offline",
                "roads_blocked", "hazard_radius_m", "hazard_area_km2"):
        if key not in b or key not in a:
            continue
        bv, av = float(b[key]), float(a[key])
        delta = av - bv
        rows.append({
            "entity_id": key,
            "metric": key,
            "baseline": round(bv, 2),
            "with_measures": round(av, 2),
            "delta": round(delta, 2),
            "pct_change": round(100.0 * delta / bv, 1) if bv else 0.0,
            "improved": delta < 0,
        })
        res.add(f"{key}_avoided", round(-delta, 2), "count")

    res.records = rows
    improved = [r for r in rows if r["improved"]]
    res.add("metrics_improved", len(improved), "count")
    if not improved:
        res.warnings.append(
            "the selected measures changed nothing measurable for this event; "
            "check that they apply to this hazard type")
    return res
