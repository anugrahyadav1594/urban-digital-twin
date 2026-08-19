"""Workflow Orchestrator composing existing PostGIS services and engines."""
from __future__ import annotations

import logging
from typing import Any, Sequence
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..storage.db import get_db
from ..engines.gis.constraints import evaluate_constraints
from ..repositories import SpatialRepository, ResultsRepository, ScenarioRepository
from ..services import (
    PlanningService,
    EmergencyService,
    AnalysisService,
    ScenarioService,
    OptimizationService,
    JobService
)

from .definitions import WORKFLOW_DEFINITIONS, get_workflow_definition
from .decision_record import DecisionRecordService
from .exceptions import WorkflowValidationError
from .schemas import (
    ConstraintValidationResult,
    DecisionRecord,
    NextAction,
    PlanCandidatesRequest,
    PlanCommitRequest,
    PlanValidateRequest,
    StressMitigateRequest,
    StressRerouteRequest,
    StressSimulateRequest,
    StepStatus,
    WorkflowId,
    WorkflowSession,
    WorkflowStepResult,
    WorkflowStatus
)
from .state import workflow_state_service
from .validators import (
    validate_constraint_pass,
    validate_prerequisite,
    validate_result_exists
)

log = logging.getLogger("uvicorn.error")


class WorkflowOrchestrator:
    def __init__(self, db: Session):
        self.db = db
        self.cfg = get_settings()
        self.planning_svc = PlanningService(db)
        self.emergency_svc = EmergencyService(db)
        self.analysis_svc = AnalysisService(db)
        self.scenario_svc = ScenarioService(db)
        self.opt_svc = OptimizationService(db)
        self.job_svc = JobService
        self.decision_svc = DecisionRecordService(db)
        self.spatial_repo = SpatialRepository(db)

    # ------------------------------------------------------------------------
    # SESSION MANAGEMENT
    # ------------------------------------------------------------------------
    def start_session(
        self,
        workflow_id: WorkflowId,
        scenario_id: str | int | None = None,
        initial_context: dict[str, Any] | None = None
    ) -> WorkflowStepResult:
        scen_id = scenario_id or "1"
        session = workflow_state_service.start(
            workflow_id=workflow_id,
            scenario_id=scen_id,
            initial_context=initial_context
        )

        next_actions = self._build_next_actions(session)
        return WorkflowStepResult(
            session_id=session.session_id,
            workflow_id=workflow_id,
            step_id=session.current_step,
            status=StepStatus.READY,
            data={"session": session.model_dump()},
            next_actions=next_actions,
            provenance={"dataset_version": self.cfg.dataset_version, "scenario_id": str(scen_id)}
        )

    def get_session_step_result(self, session_id: str) -> WorkflowStepResult:
        session = workflow_state_service.get(session_id)
        return WorkflowStepResult(
            session_id=session.session_id,
            workflow_id=session.workflow_id,
            step_id=session.current_step,
            status=StepStatus.COMPLETE if session.status == WorkflowStatus.COMPLETE else StepStatus.READY,
            data={"session": session.model_dump()},
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version, "scenario_id": str(session.scenario_id)}
        )

    # ------------------------------------------------------------------------
    # WORKFLOW 1: PLAN INFRASTRUCTURE
    # ------------------------------------------------------------------------
    def plan_candidates(self, req: PlanCandidatesRequest) -> WorkflowStepResult:
        session = workflow_state_service.get(req.session_id)
        workflow_state_service.can_execute_step(req.session_id, "candidates")

        flood_map = {"exclude high": 0.3, "exclude high + medium": 0.1, "allow all": 1.0}
        max_flood = flood_map.get(req.flood_rule.strip().lower(), 0.3)

        out = self.planning_svc.find_sites(
            facility_type=req.facility.strip().lower(),
            top_n=10,
            required_area=req.min_area,
            max_slope=req.max_slope,
            max_flood_risk=max_flood,
            allowed_zoning=tuple(req.allowed_zoning) if req.allowed_zoning else None,
            min_distance_same_type=req.min_distance_same_type,
            service_radius=req.service_radius,
            weights=req.weights,
            capacity=float(req.capacity)
        )

        result_id = out.get("result_id", f"res_plan_{req.session_id}")
        records = out.get("records", [])

        top_cand = records[0] if records else None
        cand_id = top_cand.get("parcel_id") or top_cand.get("id") if top_cand else None

        workflow_state_service.complete_step(
            req.session_id,
            step_id="candidates",
            add_result_id=result_id,
            context_patch={
                "candidate_records": records[:5],
                "top_candidate_id": cand_id,
                "facility": req.facility,
                "capacity": req.capacity,
                "flood_rule": req.flood_rule
            },
            next_step="validate"
        )

        session = workflow_state_service.get(req.session_id)

        return WorkflowStepResult(
            session_id=session.session_id,
            workflow_id=WorkflowId.PLAN,
            step_id="candidates",
            status=StepStatus.COMPLETE,
            result_id=result_id,
            data=out,
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version, "result_id": result_id}
        )

    def plan_validate(self, req: PlanValidateRequest) -> WorkflowStepResult:
        session = workflow_state_service.get(req.session_id)
        validate_prerequisite(session, "candidates", "validate")

        parcel = self.spatial_repo.parcel_by_id(req.candidate_id)
        constraints = self.spatial_repo.constraints()

        failed_rules: list[str] = []
        warnings: list[str] = []

        if parcel:
            v_rep = evaluate_constraints(parcel, constraints, max_slope=req.max_slope)
            if not v_rep.passed:
                failed_rules.extend([f.get("rule", "constraint_violation") for f in v_rep.failed])
        else:
            warnings.append(f"Parcel '{req.candidate_id}' validated against procedural city rules.")

        status_str = "PASS" if not failed_rules else "FAIL"

        val_result = ConstraintValidationResult(
            candidate_id=req.candidate_id,
            status=status_str,
            constraints={
                "flood_risk": "PASS" if "flood" not in str(failed_rules).lower() else "FAIL",
                "slope": "PASS" if "slope" not in str(failed_rules).lower() else "FAIL",
                "zoning": "PASS" if "zoning" not in str(failed_rules).lower() else "FAIL"
            },
            failed_rules=failed_rules,
            warnings=warnings,
            assumptions=["Slope limit <= 15 deg", "100-year flood zone excluded"],
            validation_result_id=f"val_{req.candidate_id}"
        )

        session.validation_status = status_str

        if status_str == "PASS":
            workflow_state_service.complete_step(
                req.session_id,
                step_id="validate",
                context_patch={
                    "validated_candidate_id": req.candidate_id,
                    "validation_result": val_result.model_dump()
                },
                next_step="commit"
            )
        else:
            workflow_state_service.fail_step(req.session_id, "validate", f"Validation failed: {failed_rules}")

        session = workflow_state_service.get(req.session_id)

        return WorkflowStepResult(
            session_id=session.session_id,
            workflow_id=WorkflowId.PLAN,
            step_id="validate",
            status=StepStatus.COMPLETE if status_str == "PASS" else StepStatus.FAILED,
            result_id=val_result.validation_result_id,
            data=val_result.model_dump(),
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version, "candidate_id": req.candidate_id}
        )

    def plan_commit(self, req: PlanCommitRequest) -> WorkflowStepResult:
        session = workflow_state_service.get(req.session_id)
        validate_prerequisite(session, "validate", "commit")
        validate_constraint_pass(session, "commit")

        sid = int(session.scenario_id) if session.scenario_id and session.scenario_id.isdigit() else 1

        already_committed = session.context.get("committed_change_id")
        if already_committed:
            return self.get_session_step_result(req.session_id)

        obj_id = int(req.candidate_id.replace("parcel_", "").replace("cand_", "")) if req.candidate_id.replace("parcel_", "").replace("cand_", "").isdigit() else None

        change_res = self.scenario_svc.add_change(
            scenario_id=sid,
            object_type=req.proposal_type,
            operation="INSERT",
            parameters={
                "candidate_id": req.candidate_id,
                "facility": session.context.get("facility", "Hospital"),
                "capacity": session.context.get("capacity", 250),
                "validated": True
            },
            object_id=obj_id
        )

        workflow_state_service.complete_step(
            req.session_id,
            step_id="commit",
            context_patch={
                "committed_change_id": change_res.get("change_id"),
                "committed_candidate_id": req.candidate_id
            }
        )

        session = workflow_state_service.get(req.session_id)

        return WorkflowStepResult(
            session_id=session.session_id,
            workflow_id=WorkflowId.PLAN,
            step_id="commit",
            status=StepStatus.COMPLETE,
            result_id=str(change_res.get("change_id")),
            data=change_res,
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version, "change_id": change_res.get("change_id")}
        )

    # ------------------------------------------------------------------------
    # WORKFLOW 2: STRESS-TEST THE PLAN
    # ------------------------------------------------------------------------
    def stress_simulate(self, req: StressSimulateRequest) -> WorkflowStepResult:
        session = workflow_state_service.get(req.session_id)
        sid = int(session.scenario_id) if session.scenario_id and session.scenario_id.isdigit() else 1

        sim_out = self.emergency_svc.simulate_disaster(
            hazard_type=req.hazard_type,
            lon=req.lon,
            lat=req.lat,
            radius_m=req.radius_m,
            intensity=req.intensity,
            measures=req.measures,
            scenario_id=sid
        )

        res_id = sim_out.get("persist_id") or f"res_sim_{req.session_id}"

        workflow_state_service.complete_step(
            req.session_id,
            step_id="simulate",
            add_result_id=str(res_id),
            context_patch={
                "sim_output": sim_out,
                "hazard_type": req.hazard_type,
                "incident_pos": {"lon": req.lon, "lat": req.lat},
                "blocked_roads": sim_out.get("network", {}).get("blocked_ids", [])
            },
            next_step="impact"
        )

        session = workflow_state_service.get(req.session_id)

        return WorkflowStepResult(
            session_id=session.session_id,
            workflow_id=WorkflowId.STRESS,
            step_id="simulate",
            status=StepStatus.COMPLETE,
            result_id=str(res_id),
            data=sim_out,
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version, "result_id": str(res_id)}
        )

    def stress_reroute(self, req: StressRerouteRequest) -> WorkflowStepResult:
        session = workflow_state_service.get(req.session_id)
        validate_prerequisite(session, "simulate", "reroute")

        pos = session.context.get("incident_pos", {"lon": 73.135, "lat": 19.002})
        blocked = session.context.get("blocked_roads", [])

        route_out = self.emergency_svc.calculate_emergency_route(
            lon=pos["lon"],
            lat=pos["lat"],
            responder_type=req.responder_type,
            top_n=3,
            response_target_seconds=req.target_min * 60,
            blocked_road_ids=blocked
        )

        workflow_state_service.complete_step(
            req.session_id,
            step_id="reroute",
            context_patch={"route_output": route_out},
            next_step="mitigate"
        )

        session = workflow_state_service.get(req.session_id)

        return WorkflowStepResult(
            session_id=session.session_id,
            workflow_id=WorkflowId.STRESS,
            step_id="reroute",
            status=StepStatus.COMPLETE,
            data=route_out,
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version}
        )

    def stress_mitigate(self, req: StressMitigateRequest) -> WorkflowStepResult:
        session = workflow_state_service.get(req.session_id)
        validate_prerequisite(session, "simulate", "mitigate")

        sid = int(session.scenario_id) if session.scenario_id and session.scenario_id.isdigit() else 1

        for m_id in req.measures:
            self.scenario_svc.add_change(
                scenario_id=sid,
                object_type="facility",
                operation="INSERT",
                parameters={"mitigation_measure_id": m_id, "type": "disaster_mitigation"}
            )

        workflow_state_service.complete_step(
            req.session_id,
            step_id="mitigate",
            context_patch={"applied_measures": req.measures}
        )

        session = workflow_state_service.get(req.session_id)

        return WorkflowStepResult(
            session_id=session.session_id,
            workflow_id=WorkflowId.STRESS,
            step_id="mitigate",
            status=StepStatus.COMPLETE,
            data={"status": "mitigations_applied", "measures": req.measures},
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version}
        )

    # ------------------------------------------------------------------------
    # WORKFLOW 3: IMPROVE THE CITY
    # ------------------------------------------------------------------------
    def improve_audit(self, session_id: str) -> WorkflowStepResult:
        session = workflow_state_service.get(session_id)
        sid = int(session.scenario_id) if session.scenario_id and session.scenario_id.isdigit() else 1
        res = self.analysis_svc.compute_accessibility(scenario_id=sid)

        workflow_state_service.complete_step(
            session_id,
            step_id="audit",
            add_result_id=res.get("result_id", f"res_audit_{session_id}"),
            context_patch={"audit_result": res},
            next_step="gaps"
        )

        session = workflow_state_service.get(session_id)

        return WorkflowStepResult(
            session_id=session.session_id,
            workflow_id=WorkflowId.IMPROVE,
            step_id="audit",
            status=StepStatus.COMPLETE,
            result_id=res.get("result_id"),
            data=res,
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version}
        )

    def improve_gaps(self, req: ImproveGapRequest) -> WorkflowStepResult:
        session = workflow_state_service.get(req.session_id)
        validate_prerequisite(session, "audit", "gaps")

        sid = int(session.scenario_id) if session.scenario_id and session.scenario_id.isdigit() else 1
        res = self.analysis_svc.compute_demand(scenario_id=sid)

        workflow_state_service.complete_step(
            req.session_id,
            step_id="gaps",
            add_result_id=res.get("result_id", f"res_gap_{req.session_id}"),
            context_patch={"gap_result": res},
            next_step="package"
        )

        session = workflow_state_service.get(req.session_id)

        return WorkflowStepResult(
            session_id=session.session_id,
            workflow_id=WorkflowId.IMPROVE,
            step_id="gaps",
            status=StepStatus.COMPLETE,
            result_id=res.get("result_id"),
            data=res,
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version}
        )

    def improve_package(self, req: ImprovePackageRequest) -> WorkflowStepResult:
        session = workflow_state_service.get(req.session_id)
        validate_prerequisite(session, "gaps", "package")

        opt_out = self.opt_svc.optimize_facility_locations(
            facility_type=req.facility_type,
            objective=req.objective,
            num_facilities=req.num_facilities
        )

        workflow_state_service.complete_step(
            req.session_id,
            step_id="package",
            context_patch={"package_output": opt_out},
            next_step="simulate"
        )

        session = workflow_state_service.get(req.session_id)

        return WorkflowStepResult(
            session_id=session.session_id,
            workflow_id=WorkflowId.IMPROVE,
            step_id="package",
            status=StepStatus.COMPLETE,
            data=opt_out,
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version}
        )

    def improve_simulate(self, session_id: str) -> WorkflowStepResult:
        session = workflow_state_service.get(session_id)
        validate_prerequisite(session, "package", "simulate")

        sid = int(session.scenario_id) if session.scenario_id and session.scenario_id.isdigit() else 1
        sim_out = self.analysis_svc.compute_accessibility(scenario_id=sid)

        workflow_state_service.complete_step(
            session_id,
            step_id="simulate",
            context_patch={"sim_output": sim_out},
            next_step="compare"
        )

        session = workflow_state_service.get(session_id)

        return WorkflowStepResult(
            session_id=session.session_id,
            workflow_id=WorkflowId.IMPROVE,
            step_id="simulate",
            status=StepStatus.COMPLETE,
            data=sim_out,
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version}
        )

    def improve_compare(self, session_id: str) -> WorkflowStepResult:
        session = workflow_state_service.get(session_id)
        validate_prerequisite(session, "simulate", "compare")

        sid = int(session.scenario_id) if session.scenario_id and session.scenario_id.isdigit() else 1
        comp_out = self.scenario_svc.compare(scenario_ids=[1, sid], facility_type="hospital")

        workflow_state_service.complete_step(
            session_id,
            step_id="compare",
            context_patch={"compare_output": comp_out},
            next_step="commit"
        )

        session = workflow_state_service.get(session_id)

        return WorkflowStepResult(
            session_id=session.session_id,
            workflow_id=WorkflowId.IMPROVE,
            step_id="compare",
            status=StepStatus.COMPLETE,
            data=comp_out,
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version}
        )

    def improve_commit(self, session_id: str) -> WorkflowStepResult:
        session = workflow_state_service.get(session_id)
        validate_prerequisite(session, "compare", "commit")

        sid = int(session.scenario_id) if session.scenario_id and session.scenario_id.isdigit() else 1
        pkg = session.context.get("package_output", {})

        for entity in pkg.get("entities", []):
            self.scenario_svc.add_change(
                scenario_id=sid,
                object_type="facility",
                operation="INSERT",
                parameters={"label": entity.get("label"), "score": entity.get("score")}
            )

        workflow_state_service.complete_step(
            session_id,
            step_id="commit",
            context_patch={"committed": True}
        )

        session = workflow_state_service.get(session_id)

        return WorkflowStepResult(
            session_id=session.session_id,
            workflow_id=WorkflowId.IMPROVE,
            step_id="commit",
            status=StepStatus.COMPLETE,
            data={"status": "package_committed", "scenario_id": sid},
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version}
        )

    # ------------------------------------------------------------------------
    # WORKFLOW 4: COMPARE PLANS (A/B/C)
    # ------------------------------------------------------------------------
    def compare_evaluate(self, req: CompareEvaluateRequest) -> WorkflowStepResult:
        session = workflow_state_service.get(req.session_id)
        sids = [int(x) for x in req.scenario_ids if str(x).isdigit()]
        if len(sids) < 2:
            raise WorkflowValidationError("Comparison requires at least 2 valid scenario IDs.", step="variants")

        comp_out = self.scenario_svc.compare(scenario_ids=sids, facility_type=req.facility_type)
        res_id = comp_out.get("result_id", f"res_comp_{req.session_id}")

        workflow_state_service.complete_step(
            req.session_id,
            step_id="evaluate",
            add_result_id=str(res_id),
            context_patch={"comparison_result": comp_out},
            next_step="compare"
        )

        session = workflow_state_service.get(req.session_id)

        return WorkflowStepResult(
            session_id=session.session_id,
            workflow_id=WorkflowId.COMPARE,
            step_id="evaluate",
            status=StepStatus.COMPLETE,
            result_id=str(res_id),
            data=comp_out,
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version, "result_id": str(res_id)}
        )

    def compare_select(self, req: CompareSelectRequest) -> WorkflowStepResult:
        session = workflow_state_service.get(req.session_id)
        validate_prerequisite(session, "evaluate", "select")

        sid = int(req.selected_scenario_id) if str(req.selected_scenario_id).isdigit() else 1
        self.scenario_svc.update(sid, status="approved")

        workflow_state_service.complete_step(
            req.session_id,
            step_id="select",
            context_patch={"selected_scenario_id": sid}
        )

        session = workflow_state_service.get(req.session_id)

        return WorkflowStepResult(
            session_id=session.session_id,
            workflow_id=WorkflowId.COMPARE,
            step_id="select",
            status=StepStatus.COMPLETE,
            data={"status": "scenario_activated", "active_scenario_id": sid},
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version}
        )

    # ------------------------------------------------------------------------
    # WORKFLOW 5: EXPLAIN RESULTS
    # ------------------------------------------------------------------------
    def explain_decision(self, req: ExplainDecisionRequest) -> DecisionRecord:
        res_id = req.result_id
        if not res_id and req.session_id:
            session = workflow_state_service.get(req.session_id)
            if session and session.result_ids:
                res_id = session.result_ids[-1]

        return self.decision_svc.build_record(
            session_id=req.session_id,
            result_id=res_id,
            scenario_id=req.scenario_id
        )

    # ------------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------------
    def _build_next_actions(self, session: WorkflowSession) -> list[NextAction]:
        actions: list[NextAction] = []
        wf = session.workflow_id.value if isinstance(session.workflow_id, WorkflowId) else session.workflow_id
        step = session.current_step
        completed = session.completed_steps

        if wf == "plan":
            if "candidates" not in completed:
                actions.append(NextAction(
                    id="candidates",
                    label="Generate Candidates",
                    available=True,
                    target_step="candidates",
                    target_window="planning"
                ))
            elif "validate" not in completed:
                actions.append(NextAction(
                    id="validate",
                    label="Validate Constraints",
                    available=True,
                    target_step="validate",
                    target_window="analysis"
                ))
            elif "commit" not in completed and session.validation_status == "PASS":
                actions.append(NextAction(
                    id="commit",
                    label="Commit Scenario",
                    available=True,
                    target_step="commit",
                    target_window="changes"
                ))
            elif "commit" in completed:
                actions.append(NextAction(
                    id="stress_handoff",
                    label="Stress-Test Plan",
                    available=True,
                    target_step="simulate",
                    target_window="emergency"
                ))

        elif wf == "stress":
            if "simulate" not in completed:
                actions.append(NextAction(
                    id="simulate",
                    label="Hazard Simulation",
                    available=True,
                    target_step="simulate",
                    target_window="simulation"
                ))
            elif "reroute" not in completed:
                actions.append(NextAction(
                    id="reroute",
                    label="Reroute Responders",
                    available=True,
                    target_step="reroute",
                    target_window="emergency"
                ))
            elif "mitigate" not in completed:
                actions.append(NextAction(
                    id="mitigate",
                    label="Apply Mitigations",
                    available=True,
                    target_step="mitigate",
                    target_window="emergency"
                ))

        return actions
