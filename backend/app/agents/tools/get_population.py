from app.agents.tools.contracts import PopulationRequest, PopulationResponse


def get_population(request: PopulationRequest) -> PopulationResponse:
    """Get the population and density metrics deterministically for a location."""
    loc = request.location.lower()
    if "city" in loc or "urban" in loc or "downtown" in loc:
        pop = 750000
        density = 2500.0
    elif "suburb" in loc:
        pop = 150000
        density = 600.0
    elif "rural" in loc:
        pop = 25000
        density = 50.0
    else:
        # Default mock fallback
        pop = 120000
        density = 400.0
        
    return PopulationResponse(population=pop, density_per_sqkm=density)
