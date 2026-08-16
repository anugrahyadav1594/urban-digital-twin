"""Infrastructure demand vs capacity. ARCHITECTURE §17.1."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..contracts import EngineResult, Provenance

ALGORITHM = "simulation.infrastructure_demand"
ALGORITHM_VERSION = "0.1.0"

# Planning norms: units of capacity required per 1,000 persons.
# Prototype-level defaults; override via the standards argument.
SERVICE_STANDARDS: dict[str, dict[str, float]] = {
    "hospital":     {"units_per_1000": 1.0,  "unit": "beds"},
    "school":       {"units_per_1000": 150.0, "unit": "seats"},
    "fire_station": {"units_per_1000": 0.02, "unit": "stations"},
    "water":        {"units_per_1000": 135000.0, "unit": "litres_per_day"},
    "clinic":       {"units_per_1000": 0.5,  "unit": "clinics"},
}


def demand_vs_capacity(
    population_zones: Sequence[Any],
    facilities: Sequence[Any],
    facility_type: str,
    provenance: Provenance,
    standards: Mapping[str, Mapping[str, float]] | None = None,
    projected_population: Mapping[str, float] | None = None,
) -> EngineResult:
    """Compare required capacity against installed capacity.

    projected_population optionally overrides current population per zone id,
    letting the same function evaluate a future horizon.
    """
    standards = standards or SERVICE_STANDARDS
    res = EngineResult(result_type="infrastructure_demand", provenance=provenance)

    std = standards.get(facility_type)
    if std is None:
        res.warnings.append(
            f"no service standard configured for '{facility_type}'; "
            "demand cannot be computed"
        )
        return res

    per_1000 = float(std["units_per_1000"])
    unit = str(std.get("unit", "units"))

    total_pop = 0.0
    for z in population_zones:
        pop = float(
            (projected_population or {}).get(str(z.id), z.population or 0.0)
        )
        total_pop += pop
        res.records.append({
            "zone_id": str(z.id),
            "population": round(pop, 1),
            "required_capacity": round(pop / 1000.0 * per_1000, 2),
        })

    installed = sum(
        float(f.capacity or 0.0) for f in facilities
        if getattr(f, "type", None) == facility_type
    )
    required = total_pop / 1000.0 * per_1000
    deficit = max(0.0, required - installed)

    res.add("population_served_basis", round(total_pop, 1), "persons")
    res.add("required_capacity", round(required, 2), unit)
    res.add("installed_capacity", round(installed, 2), unit)
    res.add("capacity_deficit", round(deficit, 2), unit)
    res.add("capacity_surplus", round(max(0.0, installed - required), 2), unit)
    res.add("utilization_ratio",
            round(required / installed, 4) if installed > 0 else None, "ratio")
    res.add("facilities_counted",
            sum(1 for f in facilities if getattr(f, "type", None) == facility_type),
            "count")

    if deficit > 0:
        res.warnings.append(
            f"capacity deficit of {deficit:.1f} {unit} for '{facility_type}'"
        )
    res.provenance = provenance.with_assumptions(
        f"service standard: {per_1000} {unit} per 1000 persons",
        "demand assumed uniform per capita across all zones",
    )
    return res
