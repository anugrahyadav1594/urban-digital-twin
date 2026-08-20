"""Unit tests for backend workflow orchestration and step gating rules."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from app.workflows.exceptions import (
    WorkflowPrerequisiteError,
    WorkflowValidationError
)
from app.workflows.orchestrator import WorkflowOrchestrator
from app.workflows.schemas import (
    CompareEvaluateRequest,
    ExplainDecisionRequest,
    PlanCandidatesRequest,
    PlanCommitRequest,
    PlanValidateRequest,
    StepStatus,
    StressMitigateRequest,
    StressRerouteRequest,
    StressSimulateRequest,
    WorkflowId
)


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def orchestrator(mock_db):
    orch = WorkflowOrchestrator(mock_db)
    orch.planning_svc.find_sites = MagicMock(return_value={
        "result_id": "res_suit_123",
        "title": "Site Suitability - Hospital",
        "records": [
            {"parcel_id": "parcel_42", "score": 88.5, "area": 6000.0}
        ]
    })
    orch.spatial_repo.parcel_by_id = MagicMock(return_value=None)
    orch.spatial_repo.constraints = MagicMock(return_value=[])
    orch.scenario_svc.add_change = MagicMock(return_value={"change_id": "chg_999", "status": "logged"})
    orch.emergency_svc.simulate_disaster = MagicMock(return_value={
        "persist_id": "res_sim_55",
        "baseline": {"population_at_risk": 4500},
        "mitigated": {"population_at_risk": 1200},
        "network": {"blocked_ids": [101, 102]}
    })
    orch.emergency_svc.calculate_emergency_route = MagicMock(return_value={
        "routes": [{"station_id": 1, "time_min": 6.2, "dispatch_order": 1}]
    })
    orch.analysis_svc.compute_accessibility = MagicMock(return_value={"result_id": "res_acc_1", "score": 75.0})
    orch.analysis_svc.compute_demand = MagicMock(return_value={"result_id": "res_dem_1", "underserved": 12000})
    orch.opt_svc.optimize_facility_locations = MagicMock(return_value={
        "entities": [{"id": "p_10", "label": "Hospital Site #1", "score": 91.0}]
    })
    orch.scenario_svc.compare = MagicMock(return_value={
        "result_id": "res_comp_1",
        "scenarios": [
            {"scenarioId": 1, "score": 0.85, "rank": 1},
            {"scenarioId": 2, "score": 0.72, "rank": 2}
        ]
    })
    orch.scenario_svc.update = MagicMock(return_value={"status": "approved"})
    return orch


def test_plan_workflow_lifecycle(orchestrator):
    start_env = orchestrator.start_session(WorkflowId.PLAN, scenario_id=1)
    sid = start_env.session_id
    assert start_env.workflow_id == WorkflowId.PLAN
    assert start_env.step_id == "requirement"

    cand_env = orchestrator.plan_candidates(PlanCandidatesRequest(
        session_id=sid,
        facility="Hospital",
        min_area=5000.0
    ))
    assert cand_env.step_id == "candidates"
    assert cand_env.status == StepStatus.COMPLETE
    assert cand_env.result_id == "res_suit_123"

    val_env = orchestrator.plan_validate(PlanValidateRequest(
        session_id=sid,
        candidate_id="parcel_42"
    ))
    assert val_env.step_id == "validate"
    assert val_env.data.get("status") == "PASS"

    commit_env = orchestrator.plan_commit(PlanCommitRequest(
        session_id=sid,
        candidate_id="parcel_42"
    ))
    assert commit_env.step_id == "commit"
    assert commit_env.status == StepStatus.COMPLETE
    assert commit_env.data.get("change_id") == "chg_999"


def test_plan_workflow_commit_rejected_without_validation(orchestrator):
    start_env = orchestrator.start_session(WorkflowId.PLAN, scenario_id=1)
    sid = start_env.session_id

    orchestrator.plan_candidates(PlanCandidatesRequest(session_id=sid))

    with pytest.raises((WorkflowPrerequisiteError, WorkflowValidationError)):
        orchestrator.plan_commit(PlanCommitRequest(session_id=sid, candidate_id="parcel_42"))


def test_stress_workflow_lifecycle(orchestrator):
    start_env = orchestrator.start_session(WorkflowId.STRESS, scenario_id=1)
    sid = start_env.session_id

    sim_env = orchestrator.stress_simulate(StressSimulateRequest(
        session_id=sid,
        hazard_type="fire",
        lon=73.135,
        lat=19.002
    ))
    assert sim_env.step_id == "simulate"
    assert sim_env.status == StepStatus.COMPLETE

    route_env = orchestrator.stress_reroute(StressRerouteRequest(
        session_id=sid,
        responder_type="fire_station"
    ))
    assert route_env.step_id == "reroute"
    assert route_env.status == StepStatus.COMPLETE

    mit_env = orchestrator.stress_mitigate(StressMitigateRequest(
        session_id=sid,
        measures=["flood_barrier_a"]
    ))
    assert mit_env.step_id == "mitigate"
    assert mit_env.status == StepStatus.COMPLETE


def test_compare_workflow_rejection_less_than_two_scenarios(orchestrator):
    start_env = orchestrator.start_session(WorkflowId.COMPARE, scenario_id=1)
    sid = start_env.session_id

    with pytest.raises(WorkflowValidationError):
        orchestrator.compare_evaluate(CompareEvaluateRequest(
            session_id=sid,
            scenario_ids=[1]
        ))


def test_explain_decision_record_missing_result(orchestrator):
    record = orchestrator.explain_decision(ExplainDecisionRequest(
        scenario_id="1"
    ))
    assert record.recommendation != ""
    assert record.overall_score is None
    assert len(record.limitations) > 0


def test_explain_decision_record_with_result(orchestrator):
    orchestrator.decision_svc.results_repo.get = MagicMock(return_value={
        "title": "Hospital Suitability Analysis",
        "records": [{"parcel_id": "parcel_42", "score": 88.5, "breakdown": {"travel": 90.0}}],
        "summary_metrics": {"population_served": {"value": 45000}}
    })
    record = orchestrator.explain_decision(ExplainDecisionRequest(
        result_id="res_suit_123",
        scenario_id="1"
    ))
    assert record.overall_score == 88.5
    assert record.affected_population == 45000
    assert len(record.benefits) > 0
