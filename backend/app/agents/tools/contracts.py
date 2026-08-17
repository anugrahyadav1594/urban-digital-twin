from pydantic import BaseModel, Field


class PopulationRequest(BaseModel):
    location: str = Field(description="The geographic area/city to get population for.")


class PopulationResponse(BaseModel):
    population: int = Field(description="Total population count.")
    density_per_sqkm: float = Field(description="Population density per square kilometer.")


class TravelTimeRequest(BaseModel):
    origin: str = Field(description="Start point or location.")
    destination: str = Field(description="End point or location.")
    mode: str = Field(default="driving", description="Mode of transport: driving, walking, transit.")


class TravelTimeResponse(BaseModel):
    travel_time_minutes: float = Field(description="Estimated travel time in minutes.")
    distance_km: float = Field(description="Estimated distance in kilometers.")


class CheckConstraintsRequest(BaseModel):
    location: str = Field(description="Location to check constraints for.")
    constraints: list[str] = Field(description="List of constraints to evaluate (e.g. 'avoid flood-prone areas').")


class CheckConstraintsResponse(BaseModel):
    violations: list[str] = Field(description="List of violated constraints.")
    passed: bool = Field(description="True if no constraints were violated.")


class EstimateCostRequest(BaseModel):
    facility_type: str = Field(description="Type of facility (e.g. hospital, school).")
    scale: str = Field(default="medium", description="Scale of project: small, medium, large.")


class EstimateCostResponse(BaseModel):
    estimated_cost_usd: float = Field(description="Estimated construction and setup cost in USD.")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0.")


class CalculateSiteScoreRequest(BaseModel):
    location: str = Field(description="Target location for scoring.")
    facility_type: str = Field(description="Type of facility.")


class CalculateSiteScoreResponse(BaseModel):
    score: float = Field(description="Suitability score between 0.0 and 100.0.")
    details: dict[str, float] = Field(description="Breakdown of score components.")
