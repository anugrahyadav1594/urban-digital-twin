from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends

from app.schemas.agent import AgentPlanRequest, AgentPlanResponse
from app.services.agent_planning_service import AgentPlanningService

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/status")
def status() -> dict[str, Any]:
    """Check the operational status of the AI layer."""
    return {
        "implemented": True,
        "reason": "multi-agent runtime fully implemented",
        "available_tools": [
            "get_population",
            "calculate_travel_time",
            "check_constraints",
            "estimate_cost",
            "calculate_site_score"
        ]
    }


@router.post("/plan", response_model=AgentPlanResponse)
def generate_agent_plan(
    request: AgentPlanRequest,
    service: AgentPlanningService = Depends(AgentPlanningService)
) -> AgentPlanResponse:
    """
    Submit an urban planning request. The orchestrator will parse the intent,
    invoke deterministic tools, run validations, and compile a finalized markdown report.
    """
    result = service.generate_plan(request.prompt)
    return AgentPlanResponse.model_validate(result)
