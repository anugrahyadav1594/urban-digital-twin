"""Pydantic schemas for the workflow orchestration layer."""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

WorkflowId = Literal["plan", "stress", "improve", "compare", "explain"]
ValidationStatus = Literal["PENDING", "PASS", "FAIL"]


class NextActionItem(BaseModel):
    id: str
    label: str
    target_step: str
    target_window: str | None = None
    available: bool = True
    description: str | None = None


class ConstraintValidationResult(BaseModel):
    candidate_id: str
    status: ValidationStatus
    constraints: dict[str, str] = Field(default_factory=dict)
    failed_rules: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    validation_result_id: str


class DecisionRecord(BaseModel):
    recommendation: str
    overall_score: float
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    constraints: dict[str, str] = Field(default_factory=dict)
    affected_population: int = 0
    benefits: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    tradeoffs: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    source_result_ids: list[str] = Field(default_factory=list)
    scenario_id: str | None = None


class WorkflowSession(BaseModel):
    session_id: str
    workflow_id: WorkflowId
    scenario_id: int | str
    current_step: str
    completed_steps: list[str] = Field(default_factory=list)
    validation_status: ValidationStatus = "PENDING"
    result_ids: list[str] = Field(default_factory=list)
    context_data: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class WorkflowResultEnvelope(BaseModel):
    workflow: WorkflowId
    session_id: str
    step: str
    status: Literal["running", "complete", "failed"]
    result: dict[str, Any] = Field(default_factory=dict)
    next_actions: list[NextActionItem] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    job_id: str | None = None


class StartWorkflowRequest(BaseModel):
    workflow_id: WorkflowId
    scenario_id: str | int | None = None
    initial_context: dict[str, Any] = Field(default_factory=dict)


class PlanCandidatesRequest(BaseModel):
    session_id: str
    facility: str = "Hospital"
    capacity: int = 250
    min_area: float = 4000.0
    max_travel_min: float = 15.0
    flood_rule: str = "Exclude High"
    weights: dict[str, float] = Field(default_factory=dict)
    max_slope: float | None = 15.0
    allowed_zoning: list[str] = Field(default_factory=list)
    min_distance_same_type: float | None = None
    service_radius: float = 2000.0


class PlanValidateRequest(BaseModel):
    session_id: str
    candidate_id: str
    max_slope: float | None = 15.0
    flood_rule: str = "Exclude High"
    allowed_zoning: list[str] = Field(default_factory=list)


class PlanCommitRequest(BaseModel):
    session_id: str
    candidate_id: str
    proposal_type: str = "facility"
    label: str | None = None


class StressSimulateRequest(BaseModel):
    session_id: str
    hazard_type: str = "fire"
    lon: float
    lat: float
    radius_m: float | None = None
    intensity: float = 1.0
    measures: list[str] = Field(default_factory=list)


class StressRerouteRequest(BaseModel):
    session_id: str
    responder_type: str = "fire_station"
    target_min: float = 8.0


class StressMitigateRequest(BaseModel):
    session_id: str
    measures: list[str] = Field(default_factory=list)


class ImproveGapRequest(BaseModel):
    session_id: str
    target_ward: str | None = None


class ImprovePackageRequest(BaseModel):
    session_id: str
    num_facilities: int = 3
    facility_type: str = "hospital"
    objective: str = "max_coverage"


class CompareEvaluateRequest(BaseModel):
    session_id: str
    scenario_ids: list[str | int]
    facility_type: str = "hospital"


class CompareSelectRequest(BaseModel):
    session_id: str
    selected_scenario_id: str | int


class ExplainDecisionRequest(BaseModel):
    session_id: str | None = None
    result_id: str | None = None
    scenario_id: str | int | None = None
