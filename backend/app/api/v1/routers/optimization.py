"""Facility location optimisation. ARCHITECTURE §5 /optimization, §15."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ...dto import analysis_dto, attach_positions
from ...deps import DbSession, Planning

router = APIRouter(prefix="/optimization", tags=["optimization"])


class OptimizeRequest(BaseModel):
    facility_type: str = "hospital"
    objective: str = "p_median"
    num_facilities: int = 3


@router.post("/facility-location")
def facility_location(req: OptimizeRequest, svc: Planning,
                      s: DbSession) -> dict[str, Any]:
    """Rank sites, then return the top-k as the siting proposal.

    Uses the MCDA ranking rather than the MIP solver so the endpoint responds
    within a request budget; §15's OR-Tools solvers belong behind a job queue.
    """
    out = svc.find_sites(req.facility_type, top_n=req.num_facilities)
    attach_positions(out.get("records", []), s, "land_parcels", "parcel_id")
    dto = analysis_dto(out, f"Facility Location - {req.num_facilities} sites",
                       layers=[{"id": "proposals", "type": "points",
                                "label": "Proposed Facilities"}])
    dto["type"] = "optimization"
    return dto
