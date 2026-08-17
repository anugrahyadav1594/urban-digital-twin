from app.agents.tools.contracts import EstimateCostRequest, EstimateCostResponse


def estimate_cost(request: EstimateCostRequest) -> EstimateCostResponse:
    """Estimate construction/development costs deterministically based on facility type and scale."""
    facility = request.facility_type.lower()
    scale = request.scale.lower()
    
    base_costs = {
        "hospital": 25000000.0,
        "medical": 18000000.0,
        "school": 8000000.0,
        "education": 6000000.0,
        "road": 3500000.0,
        "park": 750000.0,
        "housing": 12000000.0
    }
    
    # Resolve base cost
    base_cost = base_costs.get(facility, 5000000.0)
    for k, v in base_costs.items():
        if k in facility:
            base_cost = v
            break
            
    scale_multipliers = {
        "small": 0.5,
        "medium": 1.0,
        "large": 2.2
    }
    multiplier = scale_multipliers.get(scale, 1.0)
    total_cost = base_cost * multiplier
    
    return EstimateCostResponse(estimated_cost_usd=total_cost, confidence=0.90)
