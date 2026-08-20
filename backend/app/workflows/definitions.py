"""Backend workflow definitions, step sequences, and prerequisite rules."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class StepDefinition(BaseModel):
    id: str
    label: str
    description: str
    prerequisites: list[str] = Field(default_factory=list)
    target_operation: str
    allowed_next_steps: list[str] = Field(default_factory=list)
    target_window: str | None = None


class WorkflowDefinition(BaseModel):
    id: str
    title: str
    description: str
    steps: list[StepDefinition]


WORKFLOW_DEFINITIONS: dict[str, WorkflowDefinition] = {
    "plan": WorkflowDefinition(
        id="plan",
        title="Plan Infrastructure",
        description="Site suitability search, constraint validation, scenario change, and stress-test handoff.",
        steps=[
            StepDefinition(
                id="requirement",
                label="Define Requirement",
                description="Specify facility type, required area, capacity, travel time threshold, and flood rules.",
                prerequisites=[],
                target_operation="plan_start",
                allowed_next_steps=["candidates"],
                target_window="planning"
            ),
            StepDefinition(
                id="candidates",
                label="Generate Candidates",
                description="Execute PostGIS site suitability search and rank top parcel options.",
                prerequisites=["requirement"],
                target_operation="plan_candidates",
                allowed_next_steps=["validate"],
                target_window="results"
            ),
            StepDefinition(
                id="validate",
                label="Validate Constraints",
                description="Evaluate candidate against slope, 100-year flood zone, and zoning restrictions.",
                prerequisites=["candidates"],
                target_operation="plan_validate",
                allowed_next_steps=["commit"],
                target_window="analysis"
            ),
            StepDefinition(
                id="commit",
                label="Commit Scenario",
                description="Persist proposal to active scenario (requires constraint PASS).",
                prerequisites=["validate"],
                target_operation="plan_commit",
                allowed_next_steps=[],
                target_window="changes"
            )
        ]
    ),
    "stress": WorkflowDefinition(
        id="stress",
        title="Stress-Test the Plan",
        description="Simulate disaster hazard, identify blocked infrastructure, reroute responders, and apply mitigations.",
        steps=[
            StepDefinition(
                id="scenario",
                label="Select Scenario",
                description="Select active working scenario for stress-testing.",
                prerequisites=[],
                target_operation="stress_start",
                allowed_next_steps=["simulate"],
                target_window="changes"
            ),
            StepDefinition(
                id="simulate",
                label="Hazard Simulation",
                description="Run disaster flood or fire exposure simulation over scenario geometry.",
                prerequisites=["scenario"],
                target_operation="stress_simulate",
                allowed_next_steps=["impact"],
                target_window="simulation"
            ),
            StepDefinition(
                id="impact",
                label="Network Impact",
                description="Identify impassable roads, offline facilities, and cut-off population.",
                prerequisites=["simulate"],
                target_operation="stress_impact",
                allowed_next_steps=["reroute"],
                target_window="emergency"
            ),
            StepDefinition(
                id="reroute",
                label="Reroute Emergency",
                description="Calculate fastest response dispatch routes around blocked network links.",
                prerequisites=["simulate"],
                target_operation="stress_reroute",
                allowed_next_steps=["mitigate"],
                target_window="emergency"
            ),
            StepDefinition(
                id="mitigate",
                label="Apply Mitigations",
                description="Apply flood barriers or road elevations and record resilience delta in scenario.",
                prerequisites=["reroute"],
                target_operation="stress_mitigate",
                allowed_next_steps=[],
                target_window="emergency"
            )
        ]
    ),
    "improve": WorkflowDefinition(
        id="improve",
        title="Improve the City",
        description="City baseline audit, gap detection, OR-Tools optimization package, simulation, and commit.",
        steps=[
            StepDefinition(
                id="audit",
                label="Baseline Audit",
                description="Compute city-wide accessibility and population service coverage baseline.",
                prerequisites=[],
                target_operation="improve_audit",
                allowed_next_steps=["gaps"],
                target_window="analysis"
            ),
            StepDefinition(
                id="gaps",
                label="Detect Gaps",
                description="Identify underserved population wards and facility capacity deficits.",
                prerequisites=["audit"],
                target_operation="improve_gaps",
                allowed_next_steps=["package"],
                target_window="analysis"
            ),
            StepDefinition(
                id="package",
                label="Optimization Package",
                description="Run OR-Tools P-Median and Max Coverage solvers to build multi-facility development package.",
                prerequisites=["gaps"],
                target_operation="improve_package",
                allowed_next_steps=["simulate"],
                target_window="results"
            ),
            StepDefinition(
                id="simulate",
                label="Future Horizon Sim",
                description="Test development package against 2035 population projection and demand.",
                prerequisites=["package"],
                target_operation="improve_simulate",
                allowed_next_steps=["compare"],
                target_window="simulation"
            ),
            StepDefinition(
                id="compare",
                label="Baseline Comparison",
                description="Compare optimized package performance against city baseline.",
                prerequisites=["simulate"],
                target_operation="improve_compare",
                allowed_next_steps=["commit"],
                target_window="comparison"
            ),
            StepDefinition(
                id="commit",
                label="Commit Interventions",
                description="Persist development package interventions into active scenario.",
                prerequisites=["compare"],
                target_operation="improve_commit",
                allowed_next_steps=[],
                target_window="changes"
            )
        ]
    ),
    "compare": WorkflowDefinition(
        id="compare",
        title="Compare Plans",
        description="Evaluate scenario variants under common assumptions, generate trade-off matrix, and select winner.",
        steps=[
            StepDefinition(
                id="variants",
                label="Select Variants",
                description="Choose distinct scenario variants (A/B/C) to compare.",
                prerequisites=[],
                target_operation="compare_start",
                allowed_next_steps=["evaluate"],
                target_window="comparison"
            ),
            StepDefinition(
                id="evaluate",
                label="Evaluate Metrics",
                description="Run common metric battery (accessibility, resilience, cost, coverage) across variants.",
                prerequisites=["variants"],
                target_operation="compare_evaluate",
                allowed_next_steps=["compare"],
                target_window="comparison"
            ),
            StepDefinition(
                id="compare",
                label="Trade-off Matrix",
                description="Generate normalized trade-off matrix and identify algorithmic winner.",
                prerequisites=["evaluate"],
                target_operation="compare_matrix",
                allowed_next_steps=["select"],
                target_window="comparison"
            ),
            StepDefinition(
                id="select",
                label="Select Winner",
                description="Set preferred winning scenario as active working plan.",
                prerequisites=["compare"],
                target_operation="compare_select",
                allowed_next_steps=[],
                target_window="changes"
            )
        ]
    ),
    "explain": WorkflowDefinition(
        id="explain",
        title="Explain Results",
        description="Generate grounded decision record with score breakdown, constraints, assumptions, and provenance.",
        steps=[
            StepDefinition(
                id="recommendation",
                label="Primary Recommendation",
                description="State top recommended candidate or scenario option.",
                prerequisites=[],
                target_operation="explain_record",
                allowed_next_steps=["breakdown"],
                target_window="ai"
            ),
            StepDefinition(
                id="breakdown",
                label="Score Breakdown",
                description="Inspect criteria weights and accessibility metric breakdown.",
                prerequisites=["recommendation"],
                target_operation="explain_record",
                allowed_next_steps=["assumptions"],
                target_window="ai"
            ),
            StepDefinition(
                id="assumptions",
                label="Audit Assumptions",
                description="Review graph routing assumptions and flood exclusion thresholds.",
                prerequisites=["breakdown"],
                target_operation="explain_record",
                allowed_next_steps=["population"],
                target_window="ai"
            ),
            StepDefinition(
                id="population",
                label="Equity & Population",
                description="Review population coverage gain and equity distribution.",
                prerequisites=["assumptions"],
                target_operation="explain_record",
                allowed_next_steps=["rationale"],
                target_window="ai"
            ),
            StepDefinition(
                id="rationale",
                label="Decision Record",
                description="Export structured decision record and natural language explanation.",
                prerequisites=["population"],
                target_operation="explain_record",
                allowed_next_steps=[],
                target_window="ai"
            )
        ]
    )
}


def get_workflow_definition(workflow_id: str) -> WorkflowDefinition | None:
    return WORKFLOW_DEFINITIONS.get(workflow_id.lower())
