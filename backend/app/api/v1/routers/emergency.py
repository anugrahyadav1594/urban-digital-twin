"""Emergency routing and disaster simulation. ARCHITECTURE §5, §13, §17."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...deps import Emergency

router = APIRouter(prefix="/emergency", tags=["emergency"])


def _coerce_scenario(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


class RouteRequest(BaseModel):
    lon: float = Field(..., ge=-180, le=180)
    lat: float = Field(..., ge=-90, le=90)
    responderType: str = Field("fire_station")
    topN: int = Field(3, ge=1, le=10)
    turnoutSeconds: float = Field(60.0, ge=0, le=600)
    responseTargetSeconds: float = Field(480.0, gt=0, le=3600)
    blockedRoadIds: list[str] = Field(default_factory=list)
    slowedRoadIds: list[str] = Field(default_factory=list)
    scenario_id: str | int | None = None


class DisasterRequest(BaseModel):
    hazardType: str = Field("fire")
    lon: float = Field(..., ge=-180, le=180)
    lat: float = Field(..., ge=-90, le=90)
    radiusM: float | None = Field(None, gt=0, le=20000)
    intensity: float = Field(1.0, ge=0, le=1)
    measures: list[str] = Field(default_factory=list)
    responderType: str | None = None
    responseTargetSeconds: float = Field(480.0, gt=0, le=3600)
    includeRouting: bool = True
    scenario_id: str | int | None = None


class RoutePointInput(BaseModel):
    lon: float = Field(..., ge=-180, le=180)
    lat: float = Field(..., ge=-90, le=90)
    label: str | None = None


class RouteScenarioInput(BaseModel):
    name: str = Field("Simulated Hazard Scenario", min_length=1, max_length=160)
    type: str = Field("flood")
    active: bool = True
    severity_mode: str = Field("closed")
    penalty_multiplier: float = Field(3.0, ge=1.0, le=100.0)
    polygon: list[list[float]] | None = None
    center: list[float] | None = None
    radius_m: float | None = Field(None, gt=0, le=50000)
    affected_road_ids: list[str] = Field(default_factory=list)
    slowed_road_ids: list[str] = Field(default_factory=list)


class RouteCompareRequest(BaseModel):
    origin: RoutePointInput
    destination: RoutePointInput
    scenario: RouteScenarioInput = Field(default_factory=RouteScenarioInput)
    cost_metric: str = Field("time")
    scenario_id: int | str | None = None


@router.get("/catalogue")
def catalogue(svc: Emergency) -> dict[str, Any]:
    """Hazard types and mitigation measures the engine supports."""
    return svc.catalogue()


@router.post("/route")
def route(req: RouteRequest, svc: Emergency) -> dict[str, Any]:
    """Fastest routes from responding stations to an incident."""
    out = svc.find_route(
        lon=req.lon, lat=req.lat,
        responder_type=req.responderType,
        top_n=req.topN,
        turnout_seconds=req.turnoutSeconds,
        response_target_seconds=req.responseTargetSeconds,
        blocked_road_ids=req.blockedRoadIds,
        slowed_road_ids=req.slowedRoadIds,
        scenario_id=_coerce_scenario(req.scenario_id),
    )
    if "error" in out:
        raise HTTPException(409, out["error"])
    return out


@router.post("/simulate")
def simulate(req: DisasterRequest, svc: Emergency) -> dict[str, Any]:
    """Simulate a disaster with and without mitigation measures."""
    out = svc.simulate(
        hazard_type=req.hazardType, lon=req.lon, lat=req.lat,
        radius_m=req.radiusM, intensity=req.intensity,
        measures=req.measures, responder_type=req.responderType,
        response_target_seconds=req.responseTargetSeconds,
        include_routing=req.includeRouting,
        scenario_id=_coerce_scenario(req.scenario_id),
    )
    if "error" in out:
        raise HTTPException(422, out["error"])
    return out


@router.post("/route-compare")
def route_compare(req: RouteCompareRequest, svc: Emergency) -> dict[str, Any]:
    """Compare baseline and hazard-aware routes between origin and destination."""
    try:
        out = svc.compare_od_routes(
            origin_lon=req.origin.lon,
            origin_lat=req.origin.lat,
            destination_lon=req.destination.lon,
            destination_lat=req.destination.lat,
            scenario_name=req.scenario.name,
            scenario_type=req.scenario.type,
            active=req.scenario.active,
            severity_mode=req.scenario.severity_mode,
            penalty_multiplier=req.scenario.penalty_multiplier,
            polygon_lonlat=req.scenario.polygon,
            center_lonlat=req.scenario.center,
            radius_m=req.scenario.radius_m,
            affected_road_ids=req.scenario.affected_road_ids,
            slowed_road_ids=req.scenario.slowed_road_ids,
            cost_metric=req.cost_metric,
            scenario_id=_coerce_scenario(req.scenario_id),
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if "error" in out:
        raise HTTPException(409, out["error"])
    return out

