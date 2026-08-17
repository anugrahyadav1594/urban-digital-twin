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


@router.get("/scenarios")
def list_scenarios(repo: ScenarioRepo) -> list[dict[str, Any]]:
    return [scenario_dto(r, repo.changes(int(r["id"]))) for r in repo.list()]


@router.post("/scenarios", status_code=201)
def create_scenario(body: ScenarioCreate, svc: Scenarios) -> dict[str, Any]:
    out = svc.create(body.name, body.description)
    return {"scenario_id": out["scenario_id"], "id": str(out["scenario_id"]),
            "name": body.name, "status": "draft"}


@router.post("/scenarios/{scenario_id}/changes", status_code=201)
def add_change(scenario_id: int, body: ChangeCreate,
               svc: Scenarios) -> dict[str, Any]:
    return svc.add_change(scenario_id, body.type, body.operation,
                          body.parameters, body.object_id)


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
