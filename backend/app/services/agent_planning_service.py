from app.agents.runtime import AgentRuntime


class AgentPlanningService:
    """Service class interfacing with the AgentRuntime for AI-driven urban planning workflows."""

    def __init__(self) -> None:
        self.runtime = AgentRuntime()

    def generate_plan(self, user_request: str) -> dict:
        """Process a natural language user request and generate the full orchestrated plan."""
        return self.runtime.run_planning_flow(user_request)
