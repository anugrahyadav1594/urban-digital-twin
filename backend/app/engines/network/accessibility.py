"""Accessibility metrics. ARCHITECTURE §13, §17.

Every function returns an EngineResult so provenance travels with the numbers.
"""
from __future__ import annotations

from typing import Any, Sequence

import networkx as nx
from shapely.ops import unary_union

from ..contracts import EngineResult, Provenance
from ..gis.aggregation import population_within
from .routing import travel_time_matrix
from .service_area import service_area_polygon

ALGORITHM = "network.accessibility"
ALGORITHM_VERSION = "0.1.0"


def accessibility_metrics(
    G: nx.DiGraph,
    facilities: Sequence[Any],
    population_zones: Sequence[Any],
    provenance: Provenance,
    threshold_seconds: float = 900.0,
) -> EngineResult:
    """Population-weighted accessibility to the nearest facility.

    Origins are population-zone representative points; destinations are
    facilities. Zones with no reachable facility are reported explicitly.
    """
    res = EngineResult(result_type="accessibility", provenance=provenance)

    if not facilities:
        res.add("facilities_evaluated", 0, "count")
        res.warnings.append("no facilities supplied; accessibility undefined")
        return res
    if not population_zones:
        res.add("population_total", 0.0, "persons")
        res.warnings.append("no population zones supplied")
        return res

    origins = [z.geometry.representative_point() for z in population_zones]
    dests = [f.geometry for f in facilities]
    matrix = travel_time_matrix(G, origins, dests)

    total_pop = sum(float(z.population or 0.0) for z in population_zones)
    served_pop = 0.0
    unreachable_pop = 0.0
    weighted_sum = 0.0
    per_zone: list[dict[str, Any]] = []

    for z, row in zip(population_zones, matrix):
        pop = float(z.population or 0.0)
        reachable = [t for t in row if t is not None]
        best = min(reachable) if reachable else None
        if best is None:
            unreachable_pop += pop
        else:
            weighted_sum += best * pop
            if best <= threshold_seconds:
                served_pop += pop
        per_zone.append({
            "zone_id": str(z.id),
            "population": pop,
            "nearest_facility_seconds": None if best is None else round(best, 1),
            "within_threshold": bool(best is not None and best <= threshold_seconds),
        })

    reachable_pop = total_pop - unreachable_pop
    mean_time = (weighted_sum / reachable_pop) if reachable_pop > 0 else None

    res.records = per_zone
    res.add("population_total", round(total_pop, 1), "persons")
    res.add("population_within_threshold", round(served_pop, 1), "persons")
    res.add("coverage_ratio",
            round(served_pop / total_pop, 4) if total_pop else 0.0, "ratio")
    res.add("mean_travel_time",
            None if mean_time is None else round(mean_time, 1), "seconds")
    res.add("population_unreachable", round(unreachable_pop, 1), "persons")
    res.add("threshold", threshold_seconds, "seconds")
    res.add("facilities_evaluated", len(facilities), "count")

    if unreachable_pop > 0:
        res.warnings.append(
            f"{unreachable_pop:.0f} persons have no routable path to any facility"
        )
    return res


def population_to_facility(
    G: nx.DiGraph,
    facilities: Sequence[Any],
    population_zones: Sequence[Any],
    provenance: Provenance,
    respect_capacity: bool = True,
) -> EngineResult:
    """Assign each zone to its nearest facility, optionally capacity-aware.

    Greedy nearest-first assignment; zones are processed in ascending travel
    time so closer demand claims capacity first.
    """
    res = EngineResult(result_type="facility_assignment", provenance=provenance)
    if not facilities or not population_zones:
        res.warnings.append("facilities or population zones missing")
        return res

    origins = [z.geometry.representative_point() for z in population_zones]
    matrix = travel_time_matrix(G, origins, [f.geometry for f in facilities])

    pairs: list[tuple[float, int, int]] = []
    for zi, row in enumerate(matrix):
        for fi, t in enumerate(row):
            if t is not None:
                pairs.append((t, zi, fi))
    pairs.sort()

    remaining = {
        i: (float(f.capacity) if respect_capacity and f.capacity else float("inf"))
        for i, f in enumerate(facilities)
    }
    assigned: dict[int, dict[str, Any]] = {}
    load: dict[int, float] = {i: 0.0 for i in range(len(facilities))}

    for t, zi, fi in pairs:
        if zi in assigned:
            continue
        pop = float(population_zones[zi].population or 0.0)
        if remaining[fi] >= pop or remaining[fi] == float("inf"):
            assigned[zi] = {
                "zone_id": str(population_zones[zi].id),
                "facility_id": str(facilities[fi].id),
                "travel_time_seconds": round(t, 1),
                "population": pop,
            }
            remaining[fi] -= pop
            load[fi] += pop

    unassigned = [
        str(z.id) for i, z in enumerate(population_zones) if i not in assigned
    ]
    res.records = list(assigned.values())
    res.add("zones_assigned", len(assigned), "count")
    res.add("zones_unassigned", len(unassigned), "count")
    res.add("population_assigned",
            round(sum(a["population"] for a in assigned.values()), 1), "persons")

    for i, f in enumerate(facilities):
        cap = float(f.capacity) if f.capacity else None
        res.records.append({
            "facility_id": str(f.id),
            "assigned_population": round(load[i], 1),
            "capacity": cap,
            "utilization": round(load[i] / cap, 4) if cap else None,
        })
    if unassigned:
        res.warnings.append(
            f"{len(unassigned)} zones unassigned (capacity exhausted or unreachable)"
        )
    return res


def emergency_response(
    G: nx.DiGraph,
    stations: Sequence[Any],
    population_zones: Sequence[Any],
    provenance: Provenance,
    response_threshold_seconds: float = 480.0,
) -> EngineResult:
    """Emergency coverage against a response-time commitment (default 8 min)."""
    res = accessibility_metrics(
        G, stations, population_zones, provenance,
        threshold_seconds=response_threshold_seconds,
    )
    res.result_type = "emergency_response"
    gap = [r for r in res.records
           if "within_threshold" in r and not r["within_threshold"]]
    res.add("zones_outside_response_time", len(gap), "count")
    res.add("population_outside_response_time",
            round(sum(r["population"] for r in gap), 1), "persons")
    return res


def compare_accessibility(
    before: EngineResult, after: EngineResult, provenance: Provenance
) -> EngineResult:
    """Delta between two accessibility runs — proposed-road impact (§13)."""
    res = EngineResult(result_type="accessibility_delta", provenance=provenance)
    for name, unit in [
        ("mean_travel_time", "seconds"),
        ("coverage_ratio", "ratio"),
        ("population_within_threshold", "persons"),
        ("population_unreachable", "persons"),
    ]:
        b, a = before.value(name), after.value(name)
        if b is None or a is None:
            continue
        res.add(f"{name}_before", round(b, 4), unit)
        res.add(f"{name}_after", round(a, 4), unit)
        res.add(f"{name}_delta", round(a - b, 4), unit)
        if b != 0:
            res.add(f"{name}_pct_change", round((a - b) / abs(b) * 100.0, 2), "percent")
    return res
