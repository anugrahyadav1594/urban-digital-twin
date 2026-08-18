"""Scenario lifecycle. ARCHITECTURE §5 /scenarios, §16, §24."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...dto import analysis_dto, scenario_dto, coerce_scenario_id
from ...deps import ScenarioRepo, Scenarios

router = APIRouter(tags=["scenario"])


class ScenarioCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    horizon: int = 2035
    populationGrowthPct: float = 2.5
    description: str | None = None


class ChangeCreate(BaseModel):
    type: str = Field("facility")
    operation: str = Field("INSERT")
    parameters: dict[str, Any] = Field(default_factory=dict)
    object_id: int | None = None
    label: str | None = None


class CompareRequest(BaseModel):
    scenario_ids: list[str] = Field(..., min_length=2)
    facility_type: str = "hospital"


class ScenarioUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    horizon: int | None = None
    populationGrowthPct: float | None = None
    description: str | None = None


@router.get("/scenarios")
def list_scenarios(repo: ScenarioRepo) -> list[dict[str, Any]]:
    return [scenario_dto(r, repo.changes(int(r["id"]))) for r in repo.list()]


@router.post("/scenarios", status_code=201)
def create_scenario(body: ScenarioCreate, svc: Scenarios, repo: ScenarioRepo) -> dict[str, Any]:
    out = svc.create(
        name=body.name,
        description=body.description,
        horizon=body.horizon,
        population_growth_pct=body.populationGrowthPct
    )
    scen_id = out["scenario_id"]
    row = repo.get(scen_id)
    return scenario_dto(row, []) if row else out


@router.patch("/scenarios/{scenario_id}")
def update_scenario(scenario_id: str, body: ScenarioUpdate, svc: Scenarios, repo: ScenarioRepo) -> dict[str, Any]:
    sid = coerce_scenario_id(scenario_id)
    if sid is None:
        raise HTTPException(404, f"Scenario {scenario_id} not found")
    kwargs = {}
    if body.name is not None:
        kwargs["name"] = body.name
    if body.status is not None:
        kwargs["status"] = body.status
    if body.horizon is not None:
        kwargs["horizon"] = body.horizon
    if body.populationGrowthPct is not None:
        kwargs["population_growth_pct"] = body.populationGrowthPct
    if body.description is not None:
        kwargs["description"] = body.description

    out = svc.update(sid, **kwargs)
    if out is None:
        raise HTTPException(404, f"Scenario {scenario_id} not found")
    return scenario_dto(out, repo.changes(sid))


@router.post("/scenarios/{scenario_id}/changes", status_code=201)
def add_change(scenario_id: str, body: ChangeCreate,
               svc: Scenarios) -> dict[str, Any]:
    sid = coerce_scenario_id(scenario_id)
    if sid is None:
        raise HTTPException(422, "Invalid scenario ID")
    params = dict(body.parameters or {})
    if body.label and "label" not in params:
        params["label"] = body.label
    return svc.add_change(sid, body.type, body.operation,
                          params, body.object_id)


@router.post("/scenarios/{scenario_id}/evaluate")
def evaluate(scenario_id: int, svc: Scenarios,
             facility_type: str = "hospital") -> list[dict[str, Any]]:
    results = svc.evaluate(scenario_id, facility_type)
    return [analysis_dto(r.to_dict(), f"Scenario {scenario_id} - {r.result_type}")
            for r in results]


@router.post("/scenarios/compare")
def compare(body: CompareRequest, svc: Scenarios) -> dict[str, Any]:
    try:
        ids = [coerce_scenario_id(x) for x in body.scenario_ids]
        if any(i is None for i in ids):
            raise ValueError("non-numeric scenario id")
    except ValueError:
        raise HTTPException(422, "scenario_ids must be numeric")
    if len(set(ids)) < 2:
        raise HTTPException(422, "provide at least two distinct scenario_ids")
    out = svc.compare(ids, body.facility_type)
    return analysis_dto(out, "Scenario Comparison")
