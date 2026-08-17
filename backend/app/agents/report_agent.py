from app.agents.llm_client import LLMClient


class ReportAgent:
    """Agent responsible for compiling the final Markdown report from validated data and agent interpretations."""
    
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()
        
    def generate_report(
        self,
        user_request: str,
        deterministic_data: dict,
        interpretations: dict,
        validation_status: dict
    ) -> str:
        """Synthesize a structured markdown report using validated metrics and agent interpretations."""
        prompt = (
            f"Synthesize a beautifully formatted, structured, executive-level markdown report for the following urban planning request:\n"
            f"Request: \"{user_request}\"\n\n"
            f"Using the exact, validated metrics:\n"
            f"- Suitability Score: {deterministic_data.get('site_score')}/100\n"
            f"- Estimated Construction Cost: ${deterministic_data.get('estimated_cost'):,.2f} USD (Confidence: {deterministic_data.get('cost_confidence', 0.9) * 100:.1f}%)\n"
            f"- Population in Area: {deterministic_data.get('population'):,}\n"
            f"- Density: {deterministic_data.get('density'):.1f} people/sqkm\n"
            f"- Distance to nearest similar facility: {deterministic_data.get('distance_km'):.1f} km\n"
            f"- Travel time: {deterministic_data.get('travel_time_minutes'):.1f} minutes\n"
            f"- Constraint validation status: {validation_status.get('status')} (Errors/Violations: {', '.join(validation_status.get('errors', [])) or 'None'})\n\n"
            f"Incorporate the following expert interpretations:\n"
            f"- Spatial/Demographic Analysis: {interpretations.get('gis_agent')}\n"
            f"- Financial Feasibility: {interpretations.get('cost_agent')}\n"
            f"- Risk Assessment: {interpretations.get('risk_agent')}\n\n"
            f"Requirements:\n"
            f"1. Do not invent any new numbers or metrics.\n"
            f"2. Use clean markdown headings, subheadings, bullet points, and tables to make the report look highly professional.\n"
            f"3. Highlight critical warnings if constraint violations are present.\n"
            f"Return only the synthesized markdown report."
        )
        return self.llm_client.generate(prompt)
