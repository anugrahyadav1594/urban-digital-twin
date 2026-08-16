"""Spatial aggregation and population coverage. ARCHITECTURE §12."""
from __future__ import annotations

from typing import Any, Sequence

from shapely.ops import unary_union
from shapely.strtree import STRtree


def population_within(
    area: Any,
    zones: Sequence[Any],
    method: str = "areal",
) -> tuple[float, list[str]]:
    """Population inside `area`, apportioned from population zones.

    method:
      areal    — assume uniform density; split by intersected area fraction.
      centroid — a zone counts fully iff its centroid falls inside the area.

    Returns (population, assumptions) so the caller can record the method (§22).
    """
    if area is None or area.is_empty or not zones:
        return 0.0, ["no population zones intersect the area"]

    geoms = [z.geometry for z in zones]
    tree = STRtree(geoms)
    total = 0.0

    if method == "centroid":
        for i in tree.query(area):
            z = zones[int(i)]
            if area.contains(z.geometry.centroid):
                total += float(z.population or 0.0)
        return total, ["population assigned by zone centroid containment"]

    for i in tree.query(area):
        z = zones[int(i)]
        zg = z.geometry
        if zg.area <= 0:
            continue
        inter = area.intersection(zg)
        if inter.is_empty:
            continue
        total += float(z.population or 0.0) * (inter.area / zg.area)

    return total, [
        "population apportioned by areal weighting",
        "uniform population density assumed within each zone",
    ]


def coverage_ratio(
    served_area: Any,
    zones: Sequence[Any],
) -> tuple[float, float, float]:
    """(served_population, total_population, ratio 0..1)."""
    total = sum(float(z.population or 0.0) for z in zones)
    served, _ = population_within(served_area, zones)
    ratio = (served / total) if total > 0 else 0.0
    return served, total, max(0.0, min(1.0, ratio))


def aggregate_by_zone(
    features: Sequence[Any],
    zones: Sequence[Any],
    value_fn=None,
    statistic: str = "sum",
) -> dict[str, float]:
    """Aggregate feature values into zones, keyed by zone id.

    statistic: sum | count | mean | max | min
    """
    if value_fn is None:
        value_fn = lambda f: 1.0  # noqa: E731

    zone_geoms = [z.geometry for z in zones]
    tree = STRtree(zone_geoms)
    buckets: dict[str, list[float]] = {str(z.id): [] for z in zones}

    for f in features:
        g = getattr(f, "geometry", None)
        if g is None or g.is_empty:
            continue
        probe = g if g.geom_type == "Point" else g.representative_point()
        for i in tree.query(probe):
            if zone_geoms[int(i)].contains(probe):
                buckets[str(zones[int(i)].id)].append(float(value_fn(f)))
                break

    out: dict[str, float] = {}
    for zid, vals in buckets.items():
        if statistic == "count":
            out[zid] = float(len(vals))
        elif not vals:
            out[zid] = 0.0
        elif statistic == "sum":
            out[zid] = float(sum(vals))
        elif statistic == "mean":
            out[zid] = float(sum(vals) / len(vals))
        elif statistic == "max":
            out[zid] = float(max(vals))
        elif statistic == "min":
            out[zid] = float(min(vals))
        else:
            raise ValueError(f"unknown statistic: {statistic}")
    return out
