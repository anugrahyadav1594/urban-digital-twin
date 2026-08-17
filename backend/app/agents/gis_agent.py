from app.agents.llm_client import LLMClient


class GISAgent:
    """Agent responsible for explaining GIS metrics (population, travel times, density) in a natural language narrative."""
    
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()
        
    def interpret(self, location: str, population: int, density: float, travel_time: float, distance: float) -> str:
        """Interpret spatial and demographic metrics to assess suitability."""
        prompt = (
            f"As a GIS and Urban Planning Specialist, interpret and explain these demographic and spatial metrics for building a facility at '{location}':\n\n"
            f"- Location: {location}\n"
            f"- Population: {population:,}\n"
            f"- Density: {density:.1f} people/sqkm\n"
            f"- Nearest Service/Travel Distance: {distance:.1f} km\n"
            f"- Expected Travel Time: {travel_time:.1f} minutes\n\n"
            f"Provide a brief, professional interpretation explaining if this location has suitable access and demand. Keep it under 150 words."
        )
        return self.llm_client.generate(prompt)
