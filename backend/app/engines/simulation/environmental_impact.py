"""Environmental impact of a proposed footprint. ARCHITECTURE §17.1."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from shapely.ops import unary_union

from ..contracts import EngineResult, Provenance

ALGORITHM = "simulation.environmental_impact"
ALGORITHM_VERSION = "0.1.0"

# Prototype impact weights per land-cover class (0 = benign, 1 = severe loss).
DEFAULT_SENSITIVITY: dict[str, float] = {
    "forest": 1.0, "tree_cover": 1.0, "wetland": 0.95, "water": 0.9,
    "grassland": 0.6, "cropland": 0.5, "shrubland": 0.5,
    "bare": 0.2, "built": 0.05, "built_up": 0.05,
}


def environmental_impact(
    footprint: Any,
    landcover_zones: Sequence[Any] = (),
    water_bodies: Sequence[Any] = (),
    provenance: Provenance | None = None,
    sensitivity: Mapping[str, float] | None = None,
    water_buffer: float = 100.0,
) -> EngineResult:
    """Quantify land conversion caused by a proposed footprint.

    landcover_zones expose .geometry and .land_use.
    """
    sens = dict(sensitivity or DEFAULT_SENSITIVITY)
    pv = provenance or Provenance(
        dataset_version=0, algorithm=ALGORITHM, algorithm_version=ALGORITHM_VERSION
    )
    res = EngineResult(result_type="environmental_impact", provenance=pv)

    if footprint is None or footprint.is_empty:
        res.warnings.append("empty footprint; no impact computed")
        return res

    total_area = float(footprint.area)
    res.add("footprint_area", round(total_area, 2), "m2")

    converted: dict[str, float] = {}
    weighted = 0.0
    for z in landcover_zones:
        inter = footprint.intersection(z.geometry)
        if inter.is_empty:
            continue
        a = float(inter.area)
        lu = str(getattr(z, "land_use", None) or "unknown")
        converted[lu] = converted.get(lu, 0.0) + a
        weighted += a * sens.get(lu, 0.3)

    for lu, a in sorted(converted.items(), key=lambda kv: -kv[1]):
        res.records.append({
            "land_use": lu,
            "area_converted": round(a, 2),
            "share_of_footprint": round(a / total_area, 4) if total_area else None,
            "sensitivity_weight": sens.get(lu, 0.3),
        })

    green_keys = {"forest", "tree_cover", "grassland", "wetland", "shrubland"}
    green_lost = sum(a for lu, a in converted.items() if lu in green_keys)

    water_conflict = 0.0
    if water_bodies:
        buf = unary_union([w.geometry.buffer(water_buffer) for w in water_bodies])
        inter = footprint.intersection(buf)
        water_conflict = float(inter.area) if not inter.is_empty else 0.0

    res.add("area_converted", round(sum(converted.values()), 2), "m2")
    res.add("green_cover_lost", round(green_lost, 2), "m2")
    res.add("water_buffer_intrusion", round(water_conflict, 2), "m2")
    res.add("impact_index",
            round(weighted / total_area, 4) if total_area else None, "index")
    res.add("landcover_classes_affected", len(converted), "count")

    if water_conflict > 0:
        res.warnings.append(
            f"footprint intrudes {water_conflict:.0f} m2 into the "
            f"{water_buffer:.0f} m water buffer"
        )
    res.provenance = pv.with_assumptions(
        "impact index is an area-weighted land-cover sensitivity score (0-1)",
        f"water buffer of {water_buffer} m applied around water bodies",
        "no ecological field survey or species-level assessment included",
    )
    return res
