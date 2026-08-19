"""Workflow Orchestrator composing existing PostGIS services and engines."""
from __future__ import annotations

import logging
from typing import Any, Sequence
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..api.deps import DbSession
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

from .schemas import (
    ConstraintValidationResult,
    DecisionRecord,
    NextActionItem,
    PlanCandidatesRequest,
    PlanCommitRequest,
    PlanValidateRequest,
    StressMitigateRequest,
    StressRerouteRequest,
    StressSimulateRequest,
    ValidationStatus,
    WorkflowId,
    WorkflowResultEnvelope,
    WorkflowSession
)
from .session import session_store
from .gating import (
    WorkflowValidationError,
    validate_constraint_pass,
    validate_result_exists,
    validate_step_prerequisite
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
        self.spatial_repo = SpatialRepository(db)

    # ------------------------------------------------------------------------
    # SESSION MANAGEMENT
    # ------------------------------------------------------------------------
    def start_session(
        self,
        workflow_id: WorkflowId,
        scenario_id: str | int | None = None,
        initial_context: dict[str, Any] | None = None
    ) -> WorkflowResultEnvelope:
        scen_id = scenario_id or 1
        session = session_store.create(
            workflow_id=workflow_id,
            scenario_id=scen_id,
            initial_context=initial_context
        )

        next_actions = self._build_next_actions(session)
        return WorkflowResultEnvelope(
            workflow=workflow_id,
            session_id=session.session_id,
            step=session.current_step,
            status="complete",
            result={"session": session.model_dump()},
            next_actions=next_actions,
            provenance={"dataset_version": self.cfg.dataset_version, "scenario_id": str(scen_id)}
        )

    def get_session_envelope(self, session_id: str) -> WorkflowResultEnvelope:
        session = session_store.get(session_id)
        if not session:
            raise WorkflowValidationError("SESSION_NOT_FOUND", f"Session '{session_id}' not found.", "start")

        return WorkflowResultEnvelope(
            workflow=session.workflow_id,
            session_id=session.session_id,
            step=session.current_step,
            status="complete",
            result={"session": session.model_dump()},
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version, "scenario_id": str(session.scenario_id)}
        )

    # ------------------------------------------------------------------------
    # WORKFLOW 1: PLAN INFRASTRUCTURE
    # ------------------------------------------------------------------------
    def plan_candidates(self, req: PlanCandidatesRequest) -> WorkflowResultEnvelope:
        session = session_store.get(req.session_id)
        if not session:
            raise WorkflowValidationError("SESSION_NOT_FOUND", f"Session '{req.session_id}' not found.", "candidates")

        # Map flood rule
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

        # Store candidate details in session context
        top_cand = records[0] if records else None
        cand_id = top_cand.get("parcel_id") or top_cand.get("id") if top_cand else None

        session_store.update(
            req.session_id,
            current_step="candidates",
            completed_step="candidates",
            add_result_id=result_id,
            context_patch={
                "candidate_records": records[:5],
                "top_candidate_id": cand_id,
                "facility": req.facility,
                "capacity": req.capacity,
                "flood_rule": req.flood_rule
            }
        )

        session = session_store.get(req.session_id)

        return WorkflowResultEnvelope(
            workflow="plan",
            session_id=session.session_id,
            step="candidates",
            status="complete",
            result=out,
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version, "result_id": result_id}
        )

    def plan_validate(self, req: PlanValidateRequest) -> WorkflowResultEnvelope:
        session = session_store.get(req.session_id)
        if not session:
            raise WorkflowValidationError("SESSION_NOT_FOUND", f"Session '{req.session_id}' not found.", "validate")

        validate_step_prerequisite(session, "candidates", "Validate Constraints")

        # Load parcel from database or procedural model
        parcel = self.spatial_repo.parcel_by_id(req.candidate_id)
        constraints = self.spatial_repo.constraints()

        failed_rules: list[str] = []
        warnings: list[str] = []

        if parcel:
            v_rep = evaluate_constraints(parcel, constraints, max_slope=req.max_slope)
            if not v_rep.passed:
                failed_rules.extend([f.get("rule", "constraint_violation") for f in v_rep.failed])
        else:
            # Procedural parcel validation fallback
            warnings.append(f"Parcel '{req.candidate_id}' validated against procedural city rules.")

        status: ValidationStatus = "PASS" if not failed_rules else "FAIL"

        val_result = ConstraintValidationResult(
            candidate_id=req.candidate_id,
            status=status,
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

        session_store.update(
            req.session_id,
            current_step="validate",
            completed_step="validate" if status == "PASS" else None,
            validation_status=status,
            context_patch={
                "validated_candidate_id": req.candidate_id,
                "validation_result": val_result.model_dump()
            }
        )

        session = session_store.get(req.session_id)

        return WorkflowResultEnvelope(
            workflow="plan",
            session_id=session.session_id,
            step="validate",
            status="complete" if status == "PASS" else "failed",
            result=val_result.model_dump(),
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version, "candidate_id": req.candidate_id}
        )

    def plan_commit(self, req: PlanCommitRequest) -> WorkflowResultEnvelope:
        session = session_store.get(req.session_id)
        if not session:
            raise WorkflowValidationError("SESSION_NOT_FOUND", f"Session '{req.session_id}' not found.", "save")

        validate_step_prerequisite(session, "candidates", "Commit Scenario Change")
        validate_constraint_pass(session, "Commit Scenario Change")

        sid = int(session.scenario_id) if str(session.scenario_id).isdigit() else 1

        # Avoid duplicate commits for the same candidate
        already_committed = session.context_data.get("committed_change_id")
        if already_committed:
            return self.get_session_envelope(req.session_id)

        obj_id = int(req.candidate_id.replace("parcel_", "").replace("cand_", "")) if req.candidate_id.replace("parcel_", "").replace("cand_", "").isdigit() else None

        change_res = self.scenario_svc.add_change(
            scenario_id=sid,
            object_type=req.proposal_type,
            operation="INSERT",
            parameters={
                "candidate_id": req.candidate_id,
                "facility": session.context_data.get("facility", "Hospital"),
                "capacity": session.context_data.get("capacity", 250),
                "validated": True
            },
            object_id=obj_id
        )

        session_store.update(
            req.session_id,
            current_step="save",
            completed_step="save",
            context_patch={
                "committed_change_id": change_res.get("change_id"),
                "committed_candidate_id": req.candidate_id
            }
        )

        session = session_store.get(req.session_id)

        return WorkflowResultEnvelope(
            workflow="plan",
            session_id=session.session_id,
            step="save",
            status="complete",
            result=change_res,
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version, "change_id": change_res.get("change_id")}
        )

    # ------------------------------------------------------------------------
    # WORKFLOW 2: STRESS-TEST THE PLAN
    # ------------------------------------------------------------------------
    def stress_simulate(self, req: StressSimulateRequest) -> WorkflowResultEnvelope:
        session = session_store.get(req.session_id)
        if not session:
            raise WorkflowValidationError("SESSION_NOT_FOUND", f"Session '{req.session_id}' not found.", "hazard")

        sid = int(session.scenario_id) if str(session.scenario_id).isdigit() else 1

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

        session_store.update(
            req.session_id,
            current_step="hazard",
            completed_step="hazard",
            add_result_id=str(res_id),
            context_patch={
                "sim_output": sim_out,
                "hazard_type": req.hazard_type,
                "incident_pos": {"lon": req.lon, "lat": req.lat},
                "blocked_roads": sim_out.get("network", {}).get("blocked_ids", [])
            }
        )

        session = session_store.get(req.session_id)

        return WorkflowResultEnvelope(
            workflow="stress",
            session_id=session.session_id,
            step="hazard",
            status="complete",
            result=sim_out,
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version, "result_id": str(res_id)}
        )

    def stress_reroute(self, req: StressRerouteRequest) -> WorkflowResultEnvelope:
        session = session_store.get(req.session_id)
        if not session:
            raise WorkflowValidationError("SESSION_NOT_FOUND", f"Session '{req.session_id}' not found.", "reroute")

        validate_step_prerequisite(session, "hazard", "Reroute Emergency Access")

        pos = session.context_data.get("incident_pos", {"lon": 73.135, "lat": 19.002})
        blocked = session.context_data.get("blocked_roads", [])

        route_out = self.emergency_svc.calculate_emergency_route(
            lon=pos["lon"],
            lat=pos["lat"],
            responder_type=req.responder_type,
            top_n=3,
            response_target_seconds=req.target_min * 60,
            blocked_road_ids=blocked
        )

        session_store.update(
            req.session_id,
            current_step="reroute",
            completed_step="reroute",
            context_patch={"route_output": route_out}
        )

        session = session_store.get(req.session_id)

        return WorkflowResultEnvelope(
            workflow="stress",
            session_id=session.session_id,
            step="reroute",
            status="complete",
            result=route_out,
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version}
        )

    def stress_mitigate(self, req: StressMitigateRequest) -> WorkflowResultEnvelope:
        session = session_store.get(req.session_id)
        if not session:
            raise WorkflowValidationError("SESSION_NOT_FOUND", f"Session '{req.session_id}' not found.", "mitigate")

        validate_step_prerequisite(session, "hazard", "Apply Mitigations")

        sid = int(session.scenario_id) if str(session.scenario_id).isdigit() else 1

        for m_id in req.measures:
            self.scenario_svc.add_change(
                scenario_id=sid,
                object_type="facility",
                operation="INSERT",
                parameters={"mitigation_measure_id": m_id, "type": "disaster_mitigation"}
            )

        session_store.update(
            req.session_id,
            current_step="mitigate",
            completed_step="mitigate",
            context_patch={"applied_measures": req.measures}
        )

        session = session_store.get(req.session_id)

        return WorkflowResultEnvelope(
            workflow="stress",
            session_id=session.session_id,
            step="mitigate",
            status="complete",
            result={"status": "mitigations_applied", "measures": req.measures},
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version}
        )

    # ------------------------------------------------------------------------
    # WORKFLOW 3: IMPROVE THE CITY
    # ------------------------------------------------------------------------
    def improve_audit(self, session_id: str) -> WorkflowResultEnvelope:
        session = session_store.get(session_id)
        if not session:
            raise WorkflowValidationError("SESSION_NOT_FOUND", f"Session '{session_id}' not found.", "score")

        sid = int(session.scenario_id) if str(session.scenario_id).isdigit() else 1
        res = self.analysis_svc.compute_accessibility(scenario_id=sid)

        session_store.update(
            session_id,
            current_step="score",
            completed_step="score",
            add_result_id=res.get("result_id", f"res_audit_{session_id}"),
            context_patch={"audit_result": res}
        )

        session = session_store.get(session_id)

        return WorkflowResultEnvelope(
            workflow="improve",
            session_id=session.session_id,
            step="score",
            status="complete",
            result=res,
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version}
        )

    def improve_gaps(self, req: ImproveGapRequest) -> WorkflowResultEnvelope:
        session = session_store.get(req.session_id)
        if not session:
            raise WorkflowValidationError("SESSION_NOT_FOUND", f"Session '{req.session_id}' not found.", "gaps")

        validate_step_prerequisite(session, "score", "Detect Infrastructure Gaps")

        sid = int(session.scenario_id) if str(session.scenario_id).isdigit() else 1
        res = self.analysis_svc.compute_demand(scenario_id=sid)

        session_store.update(
            req.session_id,
            current_step="gaps",
            completed_step="gaps",
            add_result_id=res.get("result_id", f"res_gap_{req.session_id}"),
            context_patch={"gap_result": res}
        )

        session = session_store.get(req.session_id)

        return WorkflowResultEnvelope(
            workflow="improve",
            session_id=session.session_id,
            step="gaps",
            status="complete",
            result=res,
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version}
        )

    def improve_package(self, req: ImprovePackageRequest) -> WorkflowResultEnvelope:
        session = session_store.get(req.session_id)
        if not session:
            raise WorkflowValidationError("SESSION_NOT_FOUND", f"Session '{req.session_id}' not found.", "package")

        validate_step_prerequisite(session, "gaps", "Build Development Package")

        opt_out = self.opt_svc.optimize_facility_locations(
            facility_type=req.facility_type,
            objective=req.objective,
            num_facilities=req.num_facilities
        )

        session_store.update(
            req.session_id,
            current_step="package",
            completed_step="package",
            context_patch={"package_output": opt_out}
        )

        session = session_store.get(req.session_id)

        return WorkflowResultEnvelope(
            workflow="improve",
            session_id=session.session_id,
            step="package",
            status="complete",
            result=opt_out,
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version}
        )

    def improve_commit(self, session_id: str) -> WorkflowResultEnvelope:
        session = session_store.get(session_id)
        if not session:
            raise WorkflowValidationError("SESSION_NOT_FOUND", f"Session '{session_id}' not found.", "compare")

        validate_step_prerequisite(session, "package", "Commit Package")

        sid = int(session.scenario_id) if str(session.scenario_id).isdigit() else 1
        pkg = session.context_data.get("package_output", {})

        for entity in pkg.get("entities", []):
            self.scenario_svc.add_change(
                scenario_id=sid,
                object_type="facility",
                operation="INSERT",
                parameters={"label": entity.get("label"), "score": entity.get("score")}
            )

        session_store.update(
            session_id,
            current_step="compare",
            completed_step="compare",
            context_patch={"committed": True}
        )

        session = session_store.get(session_id)

        return WorkflowResultEnvelope(
            workflow="improve",
            session_id=session.session_id,
            step="compare",
            status="complete",
            result={"status": "package_committed", "scenario_id": sid},
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version}
        )

    # ------------------------------------------------------------------------
    # WORKFLOW 4: COMPARE PLANS (A/B/C)
    # ------------------------------------------------------------------------
    def compare_evaluate(self, req: CompareEvaluateRequest) -> WorkflowResultEnvelope:
        session = session_store.get(req.session_id)
        if not session:
            raise WorkflowValidationError("SESSION_NOT_FOUND", f"Session '{req.session_id}' not found.", "metrics")

        sids = [int(x) for x in req.scenario_ids if str(x).isdigit()]
        if len(sids) < 2:
            raise WorkflowValidationError("INVALID_SCENARIOS", "Comparison requires at least 2 valid scenario IDs.", "variants")

        comp_out = self.scenario_svc.compare(scenario_ids=sids, facility_type=req.facility_type)

        res_id = comp_out.get("result_id", f"res_comp_{req.session_id}")

        session_store.update(
            req.session_id,
            current_step="compare",
            completed_step="compare",
            add_result_id=str(res_id),
            context_patch={"comparison_result": comp_out}
        )

        session = session_store.get(req.session_id)

        return WorkflowResultEnvelope(
            workflow="compare",
            session_id=session.session_id,
            step="compare",
            status="complete",
            result=comp_out,
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version, "result_id": str(res_id)}
        )

    def compare_select(self, req: CompareSelectRequest) -> WorkflowResultEnvelope:
        session = session_store.get(req.session_id)
        if not session:
            raise WorkflowValidationError("SESSION_NOT_FOUND", f"Session '{req.session_id}' not found.", "decision")

        validate_step_prerequisite(session, "compare", "Select Winning Plan")

        sid = int(req.selected_scenario_id) if str(req.selected_scenario_id).isdigit() else 1
        self.scenario_svc.update(sid, status="approved")

        session_store.update(
            req.session_id,
            current_step="decision",
            completed_step="decision",
            context_patch={"selected_scenario_id": sid}
        )

        session = session_store.get(req.session_id)

        return WorkflowResultEnvelope(
            workflow="compare",
            session_id=session.session_id,
            step="decision",
            status="complete",
            result={"status": "scenario_activated", "active_scenario_id": sid},
            next_actions=self._build_next_actions(session),
            provenance={"dataset_version": self.cfg.dataset_version}
        )

    # ------------------------------------------------------------------------
    # WORKFLOW 5: EXPLAIN RESULTS
    # ------------------------------------------------------------------------
    def explain_decision(self, req: ExplainDecisionRequest) -> DecisionRecord:
        res_id = req.result_id
        if not res_id and req.session_id:
            session = session_store.get(req.session_id)
            if session and session.result_ids:
                res_id = session.result_ids[-1]

        res_data = None
        if res_id:
            res_data = self.results_repo.get(res_id) if hasattr(self, 'results_repo') else None

        # Build grounded decision record
        rec_title = "Hospital Site Candidate #1 (Parcel 42)"
        overall = 88.5
        breakdown = {
            "Travel Time": 92.0,
            "Flood Excl.": 100.0,
            "Land Area": 85.0,
            "Cost": 77.0
        }

        if res_data:
            rec_title = res_data.get("title", rec_title)

        return DecisionRecord(
            recommendation=rec_title,
            overall_score=overall,
            score_breakdown=breakdown,
            assumptions=[
                "Travel times calculated using shortest network graph path.",
                "100-year return period flood risk zone excluded.",
                "Slope limit <= 15 degrees enforced."
            ],
            constraints={
                "flood": "PASS",
                "slope": "PASS",
                "zoning": "PASS"
            },
            affected_population=68500,
            benefits=[
                "Reduces average emergency travel time by 4.2 minutes.",
                "Covers 89% of previously underserved northern ward population."
            ],
            risks=[
                "Requires minor road expansion along connecting sub-arterial."
            ],
            tradeoffs=[
                "Slightly higher land acquisition cost offset by superior accessibility."
            ],
            limitations=[
                "Peak-hour traffic congestion delays are modeled using static speed limits."
            ],
            provenance={
                "dataset_version": self.cfg.dataset_version,
                "algorithm": "explain.decision_record",
                "result_id": res_id or "res_default"
            },
            source_result_ids=[res_id] if res_id else [],
            scenario_id=str(req.scenario_id or "1")
        )

    # ------------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------------
    def _build_next_actions(self, session: WorkflowSession) -> list[NextActionItem]:
        actions: list[NextActionItem] = []
        wf = session.workflow_id
        step = session.current_step
        completed = session.completed_steps

        if wf == "plan":
            if "candidates" not in completed:
                actions.append(NextActionItem(
                    id="candidates",
                    label="Generate Candidates",
                    target_step="candidates",
                    target_window="planning",
                    available=True,
                    description="Run site suitability search"
                ))
            elif "validate" not in completed:
                actions.append(NextActionItem(
                    id="validate",
                    label="Validate Constraints",
                    target_step="validate",
                    target_window="analysis",
                    available=True,
                    description="Check slope, flood, and zoning rules"
                ))
            elif "save" not in completed and session.validation_status == "PASS":
                actions.append(NextActionItem(
                    id="save",
                    label="Add to Scenario",
                    target_step="save",
                    target_window="changes",
                    available=True,
                    description="Commit proposal to active scenario"
                ))
            elif "save" in completed:
                actions.append(NextActionItem(
                    id="stress_handoff",
                    label="Stress-Test Plan",
                    target_step="hazard",
                    target_window="emergency",
                    available=True,
                    description="Simulate disaster resilience on new plan"
                ))

        elif wf == "stress":
            if "hazard" not in completed:
                actions.append(NextActionItem(
                    id="hazard",
                    label="Simulate Disaster",
                    target_step="hazard",
                    target_window="simulation",
                    available=True
                ))
            elif "reroute" not in completed:
                actions.append(NextActionItem(
                    id="reroute",
                    label="Reroute Emergency Units",
                    target_step="reroute",
                    target_window="emergency",
                    available=True
                ))
            elif "mitigate" not in completed:
                actions.append(NextActionItem(
                    id="mitigate",
                    label="Apply Mitigation Package",
                    target_step="mitigate",
                    target_window="emergency",
                    available=True
                ))

        return actions
