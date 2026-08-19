"""Unit tests for backend workflow orchestration and step gating rules."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from app.workflows.schemas import (
    PlanCandidatesRequest,
    PlanCommitRequest,
    PlanValidateRequest,
    StressMitigateRequest,
    StressRerouteRequest,
    StressSimulateRequest,
    CompareEvaluateRequest,
    CompareSelectRequest,
    ExplainDecisionRequest
)
from app.workflows.session import session_store
from app.workflows.gating import WorkflowValidationError
from app.workflows.orchestrator import WorkflowOrchestrator


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def orchestrator(mock_db):
    orch = WorkflowOrchestrator(mock_db)
    # Mock underlying services so tests run without live DB
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
    # 1. Start Session
    start_env = orchestrator.start_session("plan", scenario_id=1)
    sid = start_env.session_id
    assert start_env.workflow == "plan"
    assert start_env.step == "requirement"

    # 2. Candidates step
    cand_env = orchestrator.plan_candidates(PlanCandidatesRequest(
        session_id=sid,
        facility="Hospital",
        min_area=5000.0
    ))
    assert cand_env.step == "candidates"
    assert cand_env.status == "complete"
    assert cand_env.result.get("result_id") == "res_suit_123"

    # 3. Validate step
    val_env = orchestrator.plan_validate(PlanValidateRequest(
        session_id=sid,
        candidate_id="parcel_42"
    ))
    assert val_env.step == "validate"
    assert val_env.result.get("status") == "PASS"

    # 4. Commit step
    commit_env = orchestrator.plan_commit(PlanCommitRequest(
        session_id=sid,
        candidate_id="parcel_42"
    ))
    assert commit_env.step == "save"
    assert commit_env.status == "complete"
    assert commit_env.result.get("change_id") == "chg_999"


def test_plan_workflow_commit_rejected_without_validation(orchestrator):
    start_env = orchestrator.start_session("plan", scenario_id=1)
    sid = start_env.session_id

    orchestrator.plan_candidates(PlanCandidatesRequest(session_id=sid))

    # Try committing before validating -> Must fail with WorkflowValidationError
    with pytest.raises(WorkflowValidationError) as exc:
        orchestrator.plan_commit(PlanCommitRequest(session_id=sid, candidate_id="parcel_42"))

    assert exc.value.detail["error"]["code"] == "CONSTRAINT_VALIDATION_FAILED"


def test_stress_workflow_lifecycle(orchestrator):
    start_env = orchestrator.start_session("stress", scenario_id=1)
    sid = start_env.session_id

    # 1. Simulate
    sim_env = orchestrator.stress_simulate(StressSimulateRequest(
        session_id=sid,
        hazard_type="fire",
        lon=73.135,
        lat=19.002
    ))
    assert sim_env.step == "hazard"
    assert sim_env.status == "complete"

    # 2. Reroute
    route_env = orchestrator.stress_reroute(StressRerouteRequest(
        session_id=sid,
        responder_type="fire_station"
    ))
    assert route_env.step == "reroute"
    assert route_env.status == "complete"

    # 3. Mitigate
    mit_env = orchestrator.stress_mitigate(StressMitigateRequest(
        session_id=sid,
        measures=["flood_barrier_a"]
    ))
    assert mit_env.step == "mitigate"
    assert mit_env.status == "complete"


def test_compare_workflow_rejection_less_than_two_scenarios(orchestrator):
    start_env = orchestrator.start_session("compare", scenario_id=1)
    sid = start_env.session_id

    with pytest.raises(WorkflowValidationError) as exc:
        orchestrator.compare_evaluate(CompareEvaluateRequest(
            session_id=sid,
            scenario_ids=[1]
        ))

    assert exc.value.detail["error"]["code"] == "INVALID_SCENARIOS"


def test_explain_decision_record(orchestrator):
    record = orchestrator.explain_decision(ExplainDecisionRequest(
        scenario_id="1"
    ))
    assert record.recommendation != ""
    assert record.overall_score > 0
    assert "flood" in record.constraints
    assert len(record.assumptions) > 0
    assert len(record.benefits) > 0
