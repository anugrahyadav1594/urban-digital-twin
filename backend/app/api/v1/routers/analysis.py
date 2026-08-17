"""Network analysis. ARCHITECTURE §5 /analysis, §13."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ...dto import analysis_dto, attach_positions, coerce_scenario_id
from ...deps import Analysis, DbSession

router = APIRouter(prefix="/analysis", tags=["analysis"])


class AnalysisRequest(BaseModel):
    scenario_id: str | int | None = None
    facility_type: str = "hospital"
    threshold_seconds: float = 900.0


@router.post("/accessibility")
def accessibility(req: AnalysisRequest, svc: Analysis, s: DbSession) -> dict[str, Any]:
    out = svc.accessibility(req.facility_type, req.threshold_seconds,
                            scenario_id=coerce_scenario_id(req.scenario_id))
    attach_positions(out.get("records", []), s, "population_zones", "zone_id")
    return analysis_dto(out, "Accessibility Analysis",
                        layers=[{"id": "population", "type": "heatmap",
                                 "label": "Coverage"}])


@router.post("/emergency")
def emergency(req: AnalysisRequest, svc: Analysis, s: DbSession) -> dict[str, Any]:
    out = svc.emergency_coverage(req.threshold_seconds or 480.0,
                                 scenario_id=coerce_scenario_id(req.scenario_id))
    attach_positions(out.get("records", []), s, "population_zones", "zone_id")
    return analysis_dto(out, "Emergency Response Coverage",
                        layers=[{"id": "population", "type": "heatmap",
                                 "label": "Response Time"}])


@router.post("/risk")
def risk(req: AnalysisRequest, svc: Analysis) -> dict[str, Any]:
    out = svc.resilience(scenario_id=coerce_scenario_id(req.scenario_id))
    return analysis_dto(out, "Network Resilience",
                        layers=[{"id": "roads", "type": "lines",
                                 "label": "Critical Links"}])


@router.post("/demand")
def demand(req: AnalysisRequest, svc: Analysis) -> dict[str, Any]:
    out = svc.infrastructure_demand(req.facility_type,
                                    scenario_id=coerce_scenario_id(req.scenario_id))
    return analysis_dto(out, "Infrastructure Demand")


@router.get("/accessibility")
def accessibility_get(svc: Analysis, facility_type: str = "hospital",
                      threshold_seconds: float = 900.0) -> dict[str, Any]:
    return analysis_dto(svc.accessibility(facility_type, threshold_seconds),
                        "Accessibility Analysis")
