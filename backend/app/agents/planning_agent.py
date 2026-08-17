from app.agents.llm_client import LLMClient
from app.schemas.planning import PlanningIntent


class PlanningAgent:
    """Agent responsible for parsing a user's natural language request into a structured PlanningIntent."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def plan(self, user_request: str) -> PlanningIntent:
        """Parse the user request into a structured planning intent."""
        prompt = (
            f"Analyze the following urban planning request and extract the key details:\n\n"
            f"Request: \"{user_request}\"\n\n"
            f"Extract the main objective, type of facility involved (facility_type), the target location or area "
            f"(location), list any constraints mentioned (constraints), and determine the type of analysis requested "
            f"(analysis_type - e.g. suitability, planning, comparison, optimization)."
        )
        return self.llm_client.generate_structured(prompt, PlanningIntent)
