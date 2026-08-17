from app.agents.llm_client import LLMClient


class CostAgent:
    """Agent responsible for interpreting project cost estimates and financial feasibility."""
    
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()
        
    def interpret(self, facility_type: str, scale: str, estimated_cost: float, confidence: float) -> str:
        """Interpret cost estimations and explain budget/scale implications."""
        prompt = (
            f"As a Municipal Financial Analyst, interpret this project cost estimation:\n\n"
            f"- Facility Type: {facility_type}\n"
            f"- Project Scale: {scale}\n"
            f"- Estimated Setup/Construction Cost: ${estimated_cost:,.2f} USD\n"
            f"- Estimation Confidence: {confidence * 100:.1f}%\n\n"
            f"Provide a brief financial feasibility summary, explaining the scale and cost breakdown in a municipal context. Keep it under 150 words."
        )
        return self.llm_client.generate(prompt)
