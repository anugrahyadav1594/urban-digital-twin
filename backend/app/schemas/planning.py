from pydantic import BaseModel, Field


class PlanningIntent(BaseModel):
    """Structured representation of a user's urban-planning request."""

    objective: str = Field(
        description="The main goal of the planning request."
    )

    facility_type: str | None = Field(
        default=None,
        description="Type of facility involved, if applicable."
    )

    location: str | None = Field(
        default=None,
        description="City, area, zone, or other geographic context."
    )

    constraints: list[str] = Field(
        default_factory=list,
        description="Planning constraints explicitly mentioned by the user."
    )

    analysis_type: str = Field(
        description="Type of analysis requested, such as suitability, planning, comparison, or optimization."
    )
