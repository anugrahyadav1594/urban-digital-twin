from app.agents.tools.contracts import CheckConstraintsRequest, CheckConstraintsResponse


def check_constraints(request: CheckConstraintsRequest) -> CheckConstraintsResponse:
    """Check constraints such as flood risk, slope, zoning, etc. for a given location."""
    violations = []
    loc = request.location.lower()
    
    for constraint in request.constraints:
        c_lower = constraint.lower()
        # Mock deterministic constraint evaluation
        if "flood" in c_lower and ("flood" in loc or "river" in loc or "coast" in loc or "lowland" in loc or "city" in loc):
            # Let's say city has a minor flood zone violation to make the flow interesting
            violations.append(f"Location '{request.location}' partially overlaps with a 100-year floodplain (violates: '{constraint}').")
        elif "slope" in c_lower and ("hill" in loc or "mountain" in loc or "ridge" in loc):
            violations.append(f"Location '{request.location}' exceeds the 15% slope threshold for construction (violates: '{constraint}').")
        elif "noise" in c_lower and ("highway" in loc or "airport" in loc or "industrial" in loc):
            violations.append(f"Location '{request.location}' exceeds noise thresholds (violates: '{constraint}').")
            
    return CheckConstraintsResponse(violations=violations, passed=len(violations) == 0)
