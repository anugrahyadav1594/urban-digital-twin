"""Site suitability. ARCHITECTURE §5 /planning, §14."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...dto import analysis_dto, attach_positions, coerce_scenario_id
from ...deps import DbSession, Planning

router = APIRouter(prefix="/planning", tags=["planning"])

# Frontend sends display names (frontend/types SuitabilityRequest.facility).
_FACILITY = {"hospital": "hospital", "school": "school",
             "fire station": "fire_station", "fire_station": "fire_station",
             "water treatment": "water_treatment"}
# floodRule -> max acceptable flood_risk
_FLOOD = {"exclude high": 0.6, "exclude high + medium": 0.3, "allow all": 1.0}


class SuitabilityRequest(BaseModel):
    facility: str = Field("Hospital")
    capacity: int = Field(100, ge=0)
    minArea: float = Field(5000.0, ge=0)
    maxTravelMin: float = Field(15.0, gt=0)
    floodRule: str = Field("Exclude High")
    weights: dict[str, float] = Field(default_factory=dict)
    top_n: int = Field(10, ge=1, le=50)
    scenario_id: str | int | None = None

    # Previously hidden: the service supported these all along but the API
    # never exposed them, so a planner could not express a real brief.
    maxSlope: float | None = Field(15.0, ge=0, le=90,
                                   description="degrees; null disables")
    allowedZoning: list[str] = Field(default_factory=list,
                                     description="e.g. ['R1','C1']; empty = any")
    minDistanceSameType: float | None = Field(
        None, ge=0, description="metres between same-type facilities")
    serviceRadius: float = Field(2000.0, gt=0, le=50000,
                                 description="catchment radius in metres")
    bbox: list[float] | None = Field(
        None, description="minlon,minlat,maxlon,maxlat to restrict the search")
    useNetwork: bool = Field(True,
                             description="route on the road graph; off = straight line")
    enforceMaxTravel: bool = Field(
        False, description="treat maxTravelMin as a hard rule, not just a weight")


@router.post("/suitability")
def suitability(req: SuitabilityRequest, svc: Planning,
                s: DbSession) -> dict[str, Any]:
    bbox = None
    if req.bbox:
        if len(req.bbox) != 4:
            raise HTTPException(422, "bbox must be [minlon,minlat,maxlon,maxlat]")
        bbox = tuple(float(v) for v in req.bbox)

    out = svc.find_sites(
        facility_type=_FACILITY.get(req.facility.strip().lower(), "hospital"),
        top_n=req.top_n,
        required_area=req.minArea or None,
        max_flood_risk=_FLOOD.get(req.floodRule.strip().lower(), 0.3),
        scenario_id=coerce_scenario_id(req.scenario_id),
        max_slope=req.maxSlope,
        allowed_zoning=tuple(req.allowedZoning) or None,
        min_distance_same_type=req.minDistanceSameType,
        service_radius=req.serviceRadius,
        bbox=bbox,
        use_network=req.useNetwork,
        weights=req.weights or None,
        capacity=float(req.capacity) if req.capacity else None,
        # maxTravelMin is minutes in the UI, seconds in the engine.
        max_travel_time=(req.maxTravelMin * 60.0) if req.enforceMaxTravel else None,
    )
    attach_positions(out.get("records", []), s, "land_parcels", "parcel_id")
    return analysis_dto(out, f"Site Suitability - {req.facility}",
                        layers=[{"id": "candidates", "type": "points",
                                 "label": "Candidate Sites"}])


@router.get("/criteria")
def criteria() -> dict[str, Any]:
    """Catalogue of scorable criteria, so the UI renders real controls.

    Lets the frontend build weight sliders from the engine's actual metric
    list instead of a hardcoded label set that silently mismatches.
    """
    from ....engines.planning.profile_builder import describe_criteria
    return {
        "criteria": describe_criteria(),
        "floodRules": ["Exclude High", "Exclude High + Medium", "Allow all"],
        "facilities": sorted(set(_FACILITY.values())),
    }


@router.get("/profiles")
def profiles() -> dict[str, Any]:
    from ....engines.planning import DEFAULT_PROFILES
    return {name: p.to_dict() for name, p in DEFAULT_PROFILES.items()}
