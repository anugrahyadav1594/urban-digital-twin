"""Flood exposure. ARCHITECTURE §17.1.

Overlay-based exposure against supplied hazard geometries. This is not a
hydrodynamic model — that is the optional hydro adapter (§17.2).
"""
from __future__ import annotations

from typing import Any, Sequence

from shapely.strtree import STRtree

from ..contracts import EngineResult, Provenance
from ..gis.aggregation import population_within

ALGORITHM = "simulation.flood_exposure"
ALGORITHM_VERSION = "0.1.0"


def flood_exposure(
    hazard_geoms: Sequence[Any],
    buildings: Sequence[Any] = (),
    population_zones: Sequence[Any] = (),
    facilities: Sequence[Any] = (),
    provenance: Provenance | None = None,
    return_period_years: int | None = None,
) -> EngineResult:
    """Count buildings, population and facilities inside the hazard extent."""
    from shapely.ops import unary_union

    pv = provenance or Provenance(
        dataset_version=0, algorithm=ALGORITHM, algorithm_version=ALGORITHM_VERSION
    )
    res = EngineResult(result_type="flood_exposure", provenance=pv)

    if not hazard_geoms:
        res.warnings.append("no hazard geometry supplied; exposure is zero by default")
        res.add("buildings_exposed", 0, "count")
        res.add("population_exposed", 0.0, "persons")
        return res

    hazard = unary_union(list(hazard_geoms))

    exposed_b: list[str] = []
    exposed_pop_est = 0.0
    if buildings:
        geoms = [b.geometry for b in buildings]
        tree = STRtree(geoms)
        for i in tree.query(hazard):
            b = buildings[int(i)]
            if b.geometry.intersects(hazard):
                exposed_b.append(str(b.id))
                exposed_pop_est += float(b.population_estimate or 0.0)

    pop_exposed, assumptions = (0.0, [])
    if population_zones:
        pop_exposed, assumptions = population_within(hazard, population_zones)

    exposed_f = [
        str(f.id) for f in facilities if f.geometry.intersects(hazard)
    ]

    res.records = [
        {"exposed_building_ids": exposed_b[:500]},
        {"exposed_facility_ids": exposed_f},
    ]
    res.add("hazard_area", round(hazard.area, 2), "m2")
    res.add("buildings_exposed", len(exposed_b), "count")
    res.add("buildings_total", len(buildings), "count")
    res.add("buildings_exposed_ratio",
            round(len(exposed_b) / len(buildings), 4) if buildings else None, "ratio")
    res.add("population_exposed", round(pop_exposed, 1), "persons")
    res.add("population_exposed_from_buildings", round(exposed_pop_est, 1), "persons")
    res.add("facilities_exposed", len(exposed_f), "count")
    if return_period_years:
        res.add("return_period", return_period_years, "years")

    res.provenance = pv.with_assumptions(
        *assumptions,
        "exposure determined by planar intersection with the hazard extent",
        "no flow depth, velocity or duration modelled",
    )
    if exposed_f:
        res.warnings.append(
            f"{len(exposed_f)} facilities fall inside the hazard extent"
        )
    return res
