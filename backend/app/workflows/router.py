"""FastAPI router for backend workflow orchestration. ARCHITECTURE §5."""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
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
    WorkflowResultEnvelope
)

router = APIRouter(prefix="/workflows", tags=["workflows"])


def get_orchestrator(db: Session = Depends(get_db)) -> WorkflowOrchestrator:
    return WorkflowOrchestrator(db)


@router.post("/start", response_model=WorkflowResultEnvelope)
def start_workflow(
    req: StartWorkflowRequest,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowResultEnvelope:
    return orch.start_session(
        workflow_id=req.workflow_id,
        scenario_id=req.scenario_id,
        initial_context=req.initial_context
    )


@router.get("/session/{session_id}", response_model=WorkflowResultEnvelope)
def get_session(
    session_id: str,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowResultEnvelope:
    return orch.get_session_envelope(session_id)


# ----------------------------------------------------------------------------
# PLAN INFRASTRUCTURE WORKFLOW
# ----------------------------------------------------------------------------
@router.post("/plan/candidates", response_model=WorkflowResultEnvelope)
def plan_candidates(
    req: PlanCandidatesRequest,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowResultEnvelope:
    return orch.plan_candidates(req)


@router.post("/plan/validate", response_model=WorkflowResultEnvelope)
def plan_validate(
    req: PlanValidateRequest,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowResultEnvelope:
    return orch.plan_validate(req)


@router.post("/plan/commit", response_model=WorkflowResultEnvelope)
def plan_commit(
    req: PlanCommitRequest,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowResultEnvelope:
    return orch.plan_commit(req)


# ----------------------------------------------------------------------------
# STRESS-TEST WORKFLOW
# ----------------------------------------------------------------------------
@router.post("/stress/simulate", response_model=WorkflowResultEnvelope)
def stress_simulate(
    req: StressSimulateRequest,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowResultEnvelope:
    return orch.stress_simulate(req)


@router.post("/stress/reroute", response_model=WorkflowResultEnvelope)
def stress_reroute(
    req: StressRerouteRequest,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowResultEnvelope:
    return orch.stress_reroute(req)


@router.post("/stress/mitigate", response_model=WorkflowResultEnvelope)
def stress_mitigate(
    req: StressMitigateRequest,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowResultEnvelope:
    return orch.stress_mitigate(req)


# ----------------------------------------------------------------------------
# IMPROVE THE CITY WORKFLOW
# ----------------------------------------------------------------------------
@router.post("/improve/audit/{session_id}", response_model=WorkflowResultEnvelope)
def improve_audit(
    session_id: str,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowResultEnvelope:
    return orch.improve_audit(session_id)


@router.post("/improve/gaps", response_model=WorkflowResultEnvelope)
def improve_gaps(
    req: ImproveGapRequest,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowResultEnvelope:
    return orch.improve_gaps(req)


@router.post("/improve/package", response_model=WorkflowResultEnvelope)
def improve_package(
    req: ImprovePackageRequest,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowResultEnvelope:
    return orch.improve_package(req)


@router.post("/improve/commit/{session_id}", response_model=WorkflowResultEnvelope)
def improve_commit(
    session_id: str,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowResultEnvelope:
    return orch.improve_commit(session_id)


# ----------------------------------------------------------------------------
# COMPARE PLANS WORKFLOW
# ----------------------------------------------------------------------------
@router.post("/compare/evaluate", response_model=WorkflowResultEnvelope)
def compare_evaluate(
    req: CompareEvaluateRequest,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowResultEnvelope:
    return orch.compare_evaluate(req)


@router.post("/compare/select", response_model=WorkflowResultEnvelope)
def compare_select(
    req: CompareSelectRequest,
    orch: WorkflowOrchestrator = Depends(get_orchestrator)
) -> WorkflowResultEnvelope:
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
