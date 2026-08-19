"""FastAPI router for backend workflow orchestration. ARCHITECTURE §5."""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..storage.db import get_db
from .orchestrator import WorkflowOrchestrator
from .schemas import (
    CompareEvaluateRequest,
    CompareSelectRequest,
    DecisionRecord,
    ExplainDecisionRequest,
    ImproveGapRequest,
    ImprovePackageRequest,
    PlanCandidatesRequest,
    PlanCommitRequest,
    PlanValidateRequest,
    StartWorkflowRequest,
    StressMitigateRequest,
    StressRerouteRequest,
    StressSimulateRequest,
    WorkflowStepResult
)

router = APIRouter(prefix="/workflows", tags=["workflows"])


def get_orchestrator(db: Session = Depends(get_db)) -> WorkflowOrchestrator:
    return WorkflowOrchestrator(db)


@router.post("/start", response_model=WorkflowStepResult)
def start_workflow(
    req: StartWorkflowRequest,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowStepResult:
    return orch.start_session(
        workflow_id=req.workflow_id,
        scenario_id=req.scenario_id,
        initial_context=req.initial_context
    )


@router.get("/session/{session_id}", response_model=WorkflowStepResult)
def get_session(
    session_id: str,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowStepResult:
    return orch.get_session_step_result(session_id)


# ----------------------------------------------------------------------------
# PLAN INFRASTRUCTURE WORKFLOW
# ----------------------------------------------------------------------------
@router.post("/plan/candidates", response_model=WorkflowStepResult)
def plan_candidates(
    req: PlanCandidatesRequest,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowStepResult:
    return orch.plan_candidates(req)


@router.post("/plan/validate", response_model=WorkflowStepResult)
def plan_validate(
    req: PlanValidateRequest,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowStepResult:
    return orch.plan_validate(req)


@router.post("/plan/commit", response_model=WorkflowStepResult)
def plan_commit(
    req: PlanCommitRequest,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowStepResult:
    return orch.plan_commit(req)


# ----------------------------------------------------------------------------
# STRESS-TEST WORKFLOW
# ----------------------------------------------------------------------------
@router.post("/stress/simulate", response_model=WorkflowStepResult)
def stress_simulate(
    req: StressSimulateRequest,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowStepResult:
    return orch.stress_simulate(req)


@router.post("/stress/reroute", response_model=WorkflowStepResult)
def stress_reroute(
    req: StressRerouteRequest,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowStepResult:
    return orch.stress_reroute(req)


@router.post("/stress/mitigate", response_model=WorkflowStepResult)
def stress_mitigate(
    req: StressMitigateRequest,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowStepResult:
    return orch.stress_mitigate(req)


# ----------------------------------------------------------------------------
# IMPROVE THE CITY WORKFLOW
# ----------------------------------------------------------------------------
@router.post("/improve/audit/{session_id}", response_model=WorkflowStepResult)
def improve_audit(
    session_id: str,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowStepResult:
    return orch.improve_audit(session_id)


@router.post("/improve/gaps", response_model=WorkflowStepResult)
def improve_gaps(
    req: ImproveGapRequest,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowStepResult:
    return orch.improve_gaps(req)


@router.post("/improve/package", response_model=WorkflowStepResult)
def improve_package(
    req: ImprovePackageRequest,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowStepResult:
    return orch.improve_package(req)


@router.post("/improve/simulate/{session_id}", response_model=WorkflowStepResult)
def improve_simulate(
    session_id: str,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowStepResult:
    return orch.improve_simulate(session_id)


@router.post("/improve/compare/{session_id}", response_model=WorkflowStepResult)
def improve_compare(
    session_id: str,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowStepResult:
    return orch.improve_compare(session_id)


@router.post("/improve/commit/{session_id}", response_model=WorkflowStepResult)
def improve_commit(
    session_id: str,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowStepResult:
    return orch.improve_commit(session_id)


# ----------------------------------------------------------------------------
# COMPARE PLANS WORKFLOW
# ----------------------------------------------------------------------------
@router.post("/compare/evaluate", response_model=WorkflowStepResult)
def compare_evaluate(
    req: CompareEvaluateRequest,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowStepResult:
    return orch.compare_evaluate(req)


@router.post("/compare/select", response_model=WorkflowStepResult)
def compare_select(
    req: CompareSelectRequest,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowStepResult:
    return orch.compare_select(req)


# ----------------------------------------------------------------------------
# EXPLAIN RESULTS WORKFLOW
# ----------------------------------------------------------------------------
@router.post("/explain/decision-record", response_model=DecisionRecord)
def explain_decision_record(
    req: ExplainDecisionRequest,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> DecisionRecord:
    return orch.explain_decision(req)
