from typing import Dict, Any
from app.agents.orchestrator import Orchestrator


class AgentRuntime:
    """Agent runtime managing the execution context of the planning agents."""

    def __init__(self) -> None:
        self.orchestrator = Orchestrator()

    def run_planning_flow(self, user_request: str) -> Dict[str, Any]:
        """Run the end-to-end urban planning orchestration pipeline."""
        return self.orchestrator.execute(user_request)
