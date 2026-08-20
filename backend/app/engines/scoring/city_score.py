"""Measure the ten dimensions from real spatial data. Product report §2.

Design rules followed here:

  * Reuse the deterministic engines. Accessibility comes from the existing
    network accessibility engine, not a reimplementation.
  * Never invent a number. A dimension whose inputs are missing scores None
    and is reported `measurable: false` with a reason. It is then excluded
    from the weighted aggregate rather than being silently treated as zero,
    which would punish a city for a gap in our data.
  * Show the working. Every dimension keeps its raw value, its unit and the
    counts it was derived from, so the UI can explain the score.
"""
from __future__ import annotations

import math
from typing import Any, Sequence

from ..contracts import EngineResult, Provenance
from ..planning.mcda import ScoringProfile
from .benchmarks import benchmark_for, describe as describe_benchmark
from .dimensions import (DIMENSIONS, DEFAULT_SCORING_PROFILE, DimensionScore,
                         profile_from_weights)

ALGORITHM = "city_score"
ALGORITHM_VERSION = "1.0.0"

# Facility type vocabularies. OSM tagging is inconsistent, so match loosely.
HEALTH = ("hospital", "clinic", "health", "doctor", "pharmacy", "medical")
EDUCATION = ("school", "college", "university", "kindergarten", "education")
RECREATION = ("park", "sport", "gym", "swimming", "playground", "community",
              "library", "theatre", "cultural", "stadium", "recreation")
EMERGENCY = ("fire", "police", "ambulance", "emergency")
GREEN_USES = ("park", "green", "forest", "recreation", "garden", "open_space",
              "playground")


def _typeof(f: Any) -> str:
    return str(getattr(f, "type", "") or "").lower()


def _count_matching(facilities: Sequence[Any], words: Sequence[str]) -> int:
    return sum(1 for f in facilities
               if any(w in _typeof(f) for w in words))


def _area_km2(geoms: Sequence[Any]) -> float:
    """Total area in km², assuming a projected analysis CRS (metres)."""
    total = 0.0
    for g in geoms:
        try:
            a = float(getattr(g, "area", 0.0) or 0.0)
            if math.isfinite(a):
                total += a
        except Exception:                                    # noqa: BLE001
            continue
    return total / 1e6


def _extent_km2(parcels: Sequence[Any], roads: Sequence[Any]) -> float:
    """Study-area size, from the union bounds of whatever geometry exists."""
    xs0: list[float] = []
    ys0: list[float] = []
    xs1: list[float] = []
    ys1: list[float] = []
    for coll in (parcels, roads):
        for item in coll:
            g = getattr(item, "geometry", None)
            if g is None:
                continue
            try:
                x0, y0, x1, y1 = g.bounds
            except Exception:                                # noqa: BLE001
                continue
            xs0.append(x0); ys0.append(y0); xs1.append(x1); ys1.append(y1)
    if not xs0:
        return 0.0
    w = max(xs1) - min(xs0)
    h = max(ys1) - min(ys0)
    return max(0.0, (w * h) / 1e6)


def _road_length_km(roads: Sequence[Any]) -> float:
    total = 0.0
    for r in roads:
        g = getattr(r, "geometry", None)
        if g is None:
            continue
        try:
            total += float(g.length or 0.0)
        except Exception:                                    # noqa: BLE001
            continue
    return total / 1000.0


def _shannon_mix(parcels: Sequence[Any]) -> float | None:
    """Land-use mix as normalised Shannon entropy (0..1).

    A monoculture scores 0; an even spread across categories scores 1. This
    is a standard land-use diversity measure and needs no calibration.
    """
    counts: dict[str, float] = {}
    for p in parcels:
        use = str(getattr(p, "land_use", "") or "unknown").lower()
        area = float(getattr(p, "area", 0.0) or 0.0)
        if area <= 0:
            g = getattr(p, "geometry", None)
            area = float(getattr(g, "area", 0.0) or 0.0) if g is not None else 0.0
        counts[use] = counts.get(use, 0.0) + max(area, 0.0)
    counts.pop("unknown", None)
    total = sum(counts.values())
    if total <= 0 or len(counts) < 2:
        return None
    h = 0.0
    for a in counts.values():
        p_i = a / total
        if p_i > 0:
            h -= p_i * math.log(p_i)
    return h / math.log(len(counts))


def _score_mobility(roads, parcels) -> tuple[float | None, str, dict]:
    if not roads:
        return None, "no roads in this area", {}
    area = _extent_km2(parcels, roads)
    if area <= 0:
        return None, "cannot determine study-area extent", {}
    km = _road_length_km(roads)
    return (km / area, "", {"roadKm": round(km, 1),
                            "areaKm2": round(area, 2),
                            "segments": len(roads)})


def _score_facility_access(accessibility: EngineResult | None
                           ) -> tuple[float | None, str, dict]:
    if accessibility is None:
        return None, "accessibility engine did not run", {}
    # The accessibility engine reports a 0..1 coverage_ratio; fall back to
    # deriving it from the population figures if that metric is absent.
    ratio = accessibility.value("coverage_ratio")
    pct = None if ratio is None else float(ratio) * 100.0
    if pct is None:
        served = accessibility.value("population_within_threshold")
        total = accessibility.value("population_total")
        if served is not None and total:
            pct = 100.0 * float(served) / float(total)
    if pct is None:
        return None, "accessibility produced no coverage metric", {}
    return pct, "", {
        "populationTotal": accessibility.value("population_total"),
        "populationWithinThreshold":
            accessibility.value("population_within_threshold"),
        "populationUnreachable":
            accessibility.value("population_unreachable"),
        "meanTravelSeconds": accessibility.value("mean_travel_time"),
        "thresholdSeconds": accessibility.value("threshold"),
    }


def _per_1000(count: int, population: float) -> float | None:
    if population <= 0:
        return None
    return 1000.0 * count / population


def _score_healthcare(facilities, population) -> tuple[float | None, str, dict]:
    if not facilities:
        return None, "no facilities in this area", {}
    if population <= 0:
        return None, "no population data for this area", {}
    n = _count_matching(facilities, HEALTH)
    return _per_1000(n, population), "", {"healthcareFacilities": n,
                                          "population": round(population)}


def _score_education(facilities, population) -> tuple[float | None, str, dict]:
    if not facilities:
        return None, "no facilities in this area", {}
    if population <= 0:
        return None, "no population data for this area", {}
    n = _count_matching(facilities, EDUCATION)
    return _per_1000(n, population), "", {"schools": n}


def _score_recreation(facilities, population) -> tuple[float | None, str, dict]:
    if not facilities:
        return None, "no facilities in this area", {}
    if population <= 0:
        return None, "no population data for this area", {}
    n = _count_matching(facilities, RECREATION)
    return (10000.0 * n / population if population else None), "", {
        "amenities": n}


def _score_green(parcels, population) -> tuple[float | None, str, dict]:
    if not parcels:
        return None, "no land parcels in this area", {}
    if population <= 0:
        return None, "no population data for this area", {}
    green = [p for p in parcels
             if any(w in str(getattr(p, "land_use", "") or "").lower()
                    for w in GREEN_USES)]
    if not green:
        # A real, measured zero: parcels exist but none are open space.
        return 0.0, "no open-space parcels found", {"greenParcels": 0}
    m2 = _area_km2([p.geometry for p in green if getattr(p, "geometry", None)]) * 1e6
    return m2 / population, "", {"greenParcels": len(green),
                                 "greenM2": round(m2)}


def _score_landuse(parcels) -> tuple[float | None, str, dict]:
    if not parcels:
        return None, "no land parcels in this area", {}
    mix = _shannon_mix(parcels)
    if mix is None:
        return None, "land-use attributes missing or single-category", {}
    return mix, "", {"parcels": len(parcels)}


def _score_infrastructure(parcels, roads) -> tuple[float | None, str, dict]:
    """Share of parcels with road frontage, as a serviceability proxy."""
    if not parcels or not roads:
        return None, "needs both parcels and roads", {}
    try:
        from shapely.strtree import STRtree
        geoms = [r.geometry for r in roads if getattr(r, "geometry", None)]
        if not geoms:
            return None, "roads have no geometry", {}
        tree = STRtree(geoms)
        FRONTAGE_M = 30.0
        served = 0
        for p in parcels:
            g = getattr(p, "geometry", None)
            if g is None:
                continue
            # Shapely 2.x STRtree returns integer indices.
            idx = tree.query(g.buffer(FRONTAGE_M))
            if len(idx) > 0:
                served += 1
        return (100.0 * served / len(parcels)), "", {
            "parcelsServed": served, "parcels": len(parcels),
            "frontageM": FRONTAGE_M}
    except Exception as exc:                                 # noqa: BLE001
        return None, f"frontage test failed ({type(exc).__name__})", {}


def _score_resilience(roads, facilities, graph=None
                      ) -> tuple[float | None, str, dict]:
    """Network redundancy plus emergency-service presence.

    Redundancy is the share of the network inside the largest connected
    component: fragmented networks strand responders when a road closes.
    """
    if not roads:
        return None, "no roads in this area", {}
    emergency = _count_matching(facilities or [], EMERGENCY)
    redundancy: float | None = None
    detail: dict[str, Any] = {"emergencyFacilities": emergency}

    if graph is not None:
        try:
            import networkx as nx
            und = graph.to_undirected() if graph.is_directed() else graph
            if und.number_of_nodes():
                comps = list(nx.connected_components(und))
                if comps:
                    largest = max(len(c) for c in comps)
                    redundancy = 100.0 * largest / und.number_of_nodes()
                    detail["components"] = len(comps)
                    detail["largestComponentPct"] = round(redundancy, 1)
        except Exception:                                    # noqa: BLE001
            redundancy = None

    if redundancy is None:
        return None, "routable graph unavailable", detail

    # Emergency cover modifies redundancy: a perfectly connected network with
    # no fire or ambulance station is still not resilient.
    cover = min(1.0, emergency / 3.0) if emergency else 0.0
    score = 0.7 * redundancy + 0.3 * (cover * 100.0)
    return score, "", detail


def _score_constraints(parcels) -> tuple[float | None, str, dict]:
    if not parcels:
        return None, "no land parcels in this area", {}
    risky = 0
    seen = 0
    for p in parcels:
        fr = getattr(p, "flood_risk", None)
        if fr is None:
            continue
        seen += 1
        if float(fr) >= 0.3:
            risky += 1
    if seen == 0:
        return None, "no flood-risk attributes on parcels", {}
    return (100.0 * (seen - risky) / seen), "", {
        "parcelsAssessed": seen, "constrained": risky}


def score_city(
    *,
    region: str,
    roads: Sequence[Any],
    parcels: Sequence[Any],
    facilities: Sequence[Any],
    population_zones: Sequence[Any],
    provenance: Provenance,
    accessibility: EngineResult | None = None,
    graph: Any | None = None,
    profile: ScoringProfile | None = None,
    weights: dict[str, float] | None = None,
    benchmark_raw: dict[str, float] | None = None,
    benchmark_source: str = "published",
) -> EngineResult:
    """Score one study area across all ten dimensions.

    `benchmark_raw` carries the reference city's raw values. When it comes
    from running this same function over the benchmark's own data, pass
    benchmark_source='measured' so the API can say so.
    """
    prof = profile or (profile_from_weights(weights) if weights
                       else DEFAULT_SCORING_PROFILE)
    res = EngineResult(result_type="city_score", provenance=provenance)

    population = sum(float(getattr(z, "population", 0.0) or 0.0)
                     for z in (population_zones or []))

    measured: dict[str, tuple[float | None, str, dict]] = {
        "mobility": _score_mobility(roads, parcels),
        "facility_access": _score_facility_access(accessibility),
        "healthcare": _score_healthcare(facilities, population),
        "education": _score_education(facilities, population),
        "green_space": _score_green(parcels, population),
        "recreation": _score_recreation(facilities, population),
        "landuse": _score_landuse(parcels),
        "infrastructure": _score_infrastructure(parcels, roads),
        "resilience": _score_resilience(roads, facilities, graph),
        "constraints": _score_constraints(parcels),
    }

    weights_map = prof.weights()
    bench = benchmark_raw or {}
    scored: list[DimensionScore] = []

    for dim in DIMENSIONS:
        raw, note, evidence = measured.get(dim.key, (None, "not evaluated", {}))
        pts = dim.normalise(raw)
        b_raw = bench.get(dim.key)
        ds = DimensionScore(
            key=dim.key,
            label=dim.label,
            unit=dim.unit,
            raw=None if raw is None else round(float(raw), 3),
            score=None if pts is None else round(pts, 1),
            weight=float(weights_map.get(dim.key, dim.weight)),
            measurable=pts is not None,
            note=note,
            benchmark_raw=b_raw,
            benchmark_score=(None if b_raw is None
                             else round(dim.normalise(b_raw) or 0.0, 1)),
            evidence=evidence,
        )
        scored.append(ds)

    # Weighted aggregate over measurable dimensions only. Renormalising the
    # weights is what stops a missing input from dragging the score down.
    usable = [d for d in scored if d.score is not None]
    total_w = sum(d.weight for d in usable) or 0.0
    if total_w > 0:
        overall = sum(d.score * d.weight for d in usable) / total_w
        for d in usable:
            d.contribution = round(d.score * d.weight / total_w, 2)
    else:
        overall = None

    bench_usable = [d for d in scored if d.benchmark_score is not None
                    and d.score is not None]
    bench_total_w = sum(d.weight for d in bench_usable) or 0.0
    bench_overall = (sum(d.benchmark_score * d.weight for d in bench_usable)
                     / bench_total_w) if bench_total_w > 0 else None

    res.add("overall_score", None if overall is None else round(overall, 1),
            "points")
    res.add("dimensions_measured", len(usable), "count")
    res.add("dimensions_total", len(scored), "count")
    res.add("population", round(population), "persons")
    if bench_overall is not None:
        res.add("benchmark_score", round(bench_overall, 1), "points")
        res.add("benchmark_gap", round(bench_overall - (overall or 0.0), 1),
                "points")

    unmeasured = [d for d in scored if d.score is None]
    if unmeasured:
        res.warnings.append(
            f"{len(unmeasured)} of {len(scored)} dimensions could not be "
            f"measured and are excluded from the score: "
            + ", ".join(f"{d.label} ({d.note})" for d in unmeasured)
        )

    res.records = [d.to_dict() for d in scored]
    res.artifacts.append({
        "type": "scorecard",
        "region": region,
        "benchmarkSource": benchmark_source,
    })
    return res


def scorecard_payload(result: EngineResult, region: str,
                      benchmark_source: str = "published") -> dict[str, Any]:
    """Shape a score result for the API / UI. Report §5 'City Scorecard'."""
    return {
        "region": region,
        "overallScore": result.value("overall_score"),
        "benchmarkScore": result.value("benchmark_score"),
        "benchmarkGap": result.value("benchmark_gap"),
        "benchmark": describe_benchmark(region),
        "benchmarkSource": benchmark_source,
        "population": result.value("population"),
        "dimensionsMeasured": result.value("dimensions_measured"),
        "dimensionsTotal": result.value("dimensions_total"),
        "dimensions": result.records,
        "warnings": result.warnings,
        "provenance": result.provenance.to_dict(),
    }