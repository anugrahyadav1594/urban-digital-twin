from app.agents.llm_client import LLMClient


class RiskAgent:
    """Agent responsible for interpreting constraints and assessing environmental/regulatory risk."""
    
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()
        
    def interpret(self, location: str, constraints: list[str], violations: list[str], passed: bool) -> str:
        """Provide a risk assessment explaining safety and constraint status."""
        violations_text = "\n".join([f"- {v}" for v in violations]) if violations else "No violations found."
        prompt = (
            f"As an Urban Risk Assessment Officer, interpret these constraint evaluation results for a project at '{location}':\n\n"
            f"- Target Constraints: {', '.join(constraints) if constraints else 'None specified'}\n"
            f"- Status: {'PASSED' if passed else 'FAILED'}\n"
            f"- Violations Identified:\n{violations_text}\n\n"
            f"Provide a brief risk assessment warning of environmental hazards (like flood zones) and regulatory hurdles. Keep it under 150 words."
        )
        return self.llm_client.generate(prompt)
