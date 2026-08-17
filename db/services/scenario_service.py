"""Scenario resolution and comparison against the live database.

ARCHITECTURE §16, §24. The base city tables are never mutated; scenario rows
in scenario_changes are applied as in-memory deltas.
"""
from __future__ import annotations

import json
from typing import Any, Sequence

from shapely.geometry import shape
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.engines.comparison import DEFAULT_COMPARISON, compare_scenarios
from app.engines.contracts import ScenarioChange
from app.engines.network import accessibility_metrics, build_graph
from app.engines.scenario import resolve_scenario
from app.engines.simulation import demand_vs_capacity

from db.adapters.geometry import to_analysis
from db.adapters.loaders import load_city
from db.adapters.writers import save_result

from .context import AnalysisContext

ALGORITHM_VERSION = "0.1.0"

# scenario_changes.object_type -> engine entity_type
OBJECT_TYPE_MAP = {
    "facility": "facility", "facilities": "facility",
    "road": "road", "roads": "road",
    "building": "building", "buildings": "building",
    "parcel": "parcel", "land_parcel": "parcel", "land_parcels": "parcel",
}

# scenario_changes.operation -> engine operation
OPERATION_MAP = {
    "INSERT": "add", "ADD": "add", "CREATE": "add",
    "UPDATE": "modify", "MODIFY": "modify",
    "DELETE": "delete", "REMOVE": "delete",
}


def load_scenario_changes(
    engine: Engine, scenario_id: int, analysis_srid: int
) -> list[ScenarioChange]:
    """Read scenario_changes rows and translate them into engine deltas.

    parameters JSONB may carry a 'geometry' GeoJSON member for added or moved
    objects; everything else becomes modified_attributes.
    """
    sql = text(
        "SELECT id, object_type, object_id, operation, parameters "
        "FROM scenario_changes WHERE scenario_id = :sid ORDER BY id"
    )
    out: list[ScenarioChange] = []
    with engine.connect() as conn:
        for row in conn.execute(sql, {"sid": scenario_id}).mappings():
            params = row["parameters"]
            if isinstance(params, str):
                params = json.loads(params)
            params = dict(params or {})

            geom = None
            raw_geom = params.pop("geometry", None)
            if raw_geom:
                if isinstance(raw_geom, str):
                    raw_geom = json.loads(raw_geom)
                geom = to_analysis(shape(raw_geom), analysis_srid)

            entity_type = OBJECT_TYPE_MAP.get(
                str(row["object_type"]).lower(), str(row["object_type"]).lower()
            )
            operation = OPERATION_MAP.get(
                str(row["operation"]).upper(), str(row["operation"]).lower()
            )

            out.append(ScenarioChange(
                scenario_id=str(scenario_id),
                entity_type=entity_type,
                operation=operation,
                entity_id=str(row["object_id"]) if row["object_id"] is not None else None,
                modified_attributes=params,
                proposed_geometry=geom,
            ))
    return out


def resolve(
    engine: Engine, scenario_id: int, ctx: AnalysisContext | None = None
):
    """Base city + scenario deltas = proposed state (in memory only)."""
    ctx = ctx or AnalysisContext(scenario_id=scenario_id)
    base = load_city(engine, ctx.bbox, ctx.analysis_srid)
    changes = load_scenario_changes(engine, scenario_id, ctx.analysis_srid)
    return resolve_scenario(
        base=base,
        changes=changes,
        dataset_version=ctx.dataset_version,
        scenario_id=str(scenario_id),
        scenario_version=ctx.scenario_version or 1,
    ), changes


def evaluate_scenario(
    engine: Engine,
    scenario_id: int,
    facility_type: str = "hospital",
    threshold_minutes: float = 15.0,
    ctx: AnalysisContext | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Evaluate one scenario's proposed state and persist the metrics."""
    ctx = ctx or AnalysisContext(scenario_id=scenario_id, scenario_version=1)
    city, changes = resolve(engine, scenario_id, ctx)

    if not city.roads:
        return {"error": "no roads available; run the ETL pipeline first"}

    graph = build_graph(city.roads, mode="car")
    facilities = [f for f in city.facilities if f.type == facility_type]

    prov_acc = ctx.provenance(
        "network.accessibility", ALGORITHM_VERSION,
        extra_parameters={
            "facility_type": facility_type,
            "threshold_seconds": threshold_minutes * 60.0,
            "changes_applied": len(city.applied),
        },
    )
    acc = accessibility_metrics(
        graph, facilities, city.population_zones, prov_acc,
        threshold_seconds=threshold_minutes * 60.0,
    )

    prov_cap = ctx.provenance(
        "simulation.infrastructure_demand", ALGORITHM_VERSION,
        extra_parameters={"facility_type": facility_type},
    )
    cap = demand_vs_capacity(
        city.population_zones, city.facilities, facility_type, prov_cap
    )

    ids = []
    if persist:
        ids = [save_result(engine, acc, scenario_id),
               save_result(engine, cap, scenario_id)]

    return {
        "scenario_id": scenario_id,
        "result_ids": ids,
        "changes_applied": city.applied,
        "changes_rejected": city.rejected,
        "counts": city.counts(),
        "accessibility": [m.to_dict() for m in acc.metrics],
        "capacity": [m.to_dict() for m in cap.metrics],
        "warnings": acc.warnings + cap.warnings,
        "_results": [acc, cap],
    }


def compare(
    engine: Engine,
    scenario_ids: Sequence[int],
    facility_type: str = "hospital",
    ctx: AnalysisContext | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Compare several scenarios on a common metric set (§24)."""
    base_ctx = ctx or AnalysisContext()
    bundles: dict[str, list[Any]] = {}
    per_scenario: dict[str, Any] = {}

    for sid in scenario_ids:
        sctx = AnalysisContext(
            dataset_version=base_ctx.dataset_version,
            scenario_id=sid,
            scenario_version=1,
            analysis_srid=base_ctx.analysis_srid,
            bbox=base_ctx.bbox,
        )
        evaluated = evaluate_scenario(
            engine, sid, facility_type, ctx=sctx, persist=False
        )
        if "error" in evaluated:
            return evaluated
        bundles[str(sid)] = evaluated.pop("_results")
        per_scenario[str(sid)] = evaluated

    provenance = base_ctx.provenance(
        "comparison.compare_scenarios", ALGORITHM_VERSION,
        extra_parameters={
            "scenario_ids": list(scenario_ids),
            "facility_type": facility_type,
        },
    )
    result = compare_scenarios(bundles, provenance, DEFAULT_COMPARISON)
    result_id = save_result(engine, result, None) if persist else None

    return {
        "result_id": result_id,
        "ranking": result.records,
        "metrics": [m.to_dict() for m in result.metrics],
        "warnings": result.warnings,
        "per_scenario": per_scenario,
    }
