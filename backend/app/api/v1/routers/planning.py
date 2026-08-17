"""Site suitability. ARCHITECTURE §5 /planning, §14."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
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


@router.post("/suitability")
def suitability(req: SuitabilityRequest, svc: Planning,
                s: DbSession) -> dict[str, Any]:
    out = svc.find_sites(
        facility_type=_FACILITY.get(req.facility.strip().lower(), "hospital"),
        top_n=req.top_n,
        required_area=req.minArea or None,
        max_flood_risk=_FLOOD.get(req.floodRule.strip().lower(), 0.3),
        scenario_id=coerce_scenario_id(req.scenario_id),
    )
    attach_positions(out.get("records", []), s, "land_parcels", "parcel_id")
    return analysis_dto(out, f"Site Suitability - {req.facility}",
                        layers=[{"id": "candidates", "type": "points",
                                 "label": "Candidate Sites"}])


@router.get("/profiles")
def profiles() -> dict[str, Any]:
    from ....engines.planning import DEFAULT_PROFILES
    return {name: p.to_dict() for name, p in DEFAULT_PROFILES.items()}
