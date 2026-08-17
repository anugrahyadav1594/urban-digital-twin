from app.agents.tools.contracts import CalculateSiteScoreRequest, CalculateSiteScoreResponse


def calculate_site_score(request: CalculateSiteScoreRequest) -> CalculateSiteScoreResponse:
    """Calculate site suitability score deterministically based on location and facility type."""
    loc = request.location.lower()
    
    # Deterministic scoring components
    accessibility = 85.0 if "city" in loc or "urban" in loc else 60.0
    environmental = 65.0 if "city" in loc or "urban" in loc else 90.0
    zoning = 75.0
    
    if "industrial" in loc:
        zoning = 40.0
        accessibility = 70.0
        environmental = 50.0
        
    score_components = {
        "accessibility_score": accessibility,
        "environmental_score": environmental,
        "zoning_compatibility": zoning
    }
    
    avg_score = round(sum(score_components.values()) / len(score_components), 1)
    
    return CalculateSiteScoreResponse(score=avg_score, details=score_components)
