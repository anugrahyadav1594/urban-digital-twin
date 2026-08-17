from fastapi import APIRouter, Depends
from app.schemas.agent import AgentPlanRequest, AgentPlanResponse
from app.services.planning_service import PlanningService

router = APIRouter()


@router.post("/plan", response_model=AgentPlanResponse)
def generate_agent_plan(
    request: AgentPlanRequest,
    service: PlanningService = Depends(PlanningService)
) -> AgentPlanResponse:
    """
    Submit an urban planning request. The orchestrator will parse the intent,
    invoke deterministic tools, run validations, and compile a finalized markdown report.
    """
    result = service.generate_plan(request.prompt)
    return AgentPlanResponse.model_validate(result)
