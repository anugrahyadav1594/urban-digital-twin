"""Authoritative state management service for workflow sessions."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from .definitions import get_workflow_definition
from .exceptions import (
    WorkflowNotFoundError,
    WorkflowPrerequisiteError,
    WorkflowTransitionError
)
from .schemas import (
    StepStatus,
    WorkflowId,
    WorkflowSession,
    WorkflowStatus
)


class WorkflowStateService:
    def __init__(self):
        self._sessions: dict[str, WorkflowSession] = {}

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def start(
        self,
        workflow_id: WorkflowId,
        scenario_id: str | int | None = None,
        initial_context: dict[str, Any] | None = None
    ) -> WorkflowSession:
        sid = f"wf_sess_{uuid.uuid4().hex[:12]}"
        def_obj = get_workflow_definition(workflow_id.value)
        initial_step = def_obj.steps[0].id if def_obj and def_obj.steps else "requirement"

        session = WorkflowSession(
            session_id=sid,
            workflow_id=workflow_id,
            scenario_id=str(scenario_id) if scenario_id is not None else "1",
            current_step=initial_step,
            completed_steps=[initial_step],
            status=WorkflowStatus.ACTIVE,
            context=initial_context or {},
            result_ids=[],
            validation_status="PENDING",
            created_at=self._now(),
            updated_at=self._now()
        )
        self._sessions[sid] = session
        return session

    def get(self, session_id: str) -> WorkflowSession:
        session = self._sessions.get(session_id)
        if not session:
            raise WorkflowNotFoundError(session_id)
        return session

    def can_execute_step(self, session_id: str, step_id: str) -> bool:
        session = self.get(session_id)
        def_obj = get_workflow_definition(session.workflow_id.value)
        if not def_obj:
            return True

        target = next((s for s in def_obj.steps if s.id == step_id), None)
        if not target:
            return True

        for req in target.prerequisites:
            if req not in session.completed_steps:
                raise WorkflowPrerequisiteError(required_step=req, current_step=step_id)
        return True

    def complete_step(
        self,
        session_id: str,
        step_id: str,
        add_result_id: str | None = None,
        context_patch: dict[str, Any] | None = None,
        next_step: str | None = None
    ) -> WorkflowSession:
        session = self.get(session_id)
        self.can_execute_step(session_id, step_id)

        if step_id not in session.completed_steps:
            session.completed_steps.append(step_id)

        if add_result_id and add_result_id not in session.result_ids:
            session.result_ids.append(add_result_id)

        if context_patch:
            session.context.update(context_patch)

        if next_step:
            session.current_step = next_step
        else:
            def_obj = get_workflow_definition(session.workflow_id.value)
            if def_obj:
                curr_idx = next((i for i, s in enumerate(def_obj.steps) if s.id == step_id), 0)
                if curr_idx < len(def_obj.steps) - 1:
                    session.current_step = def_obj.steps[curr_idx + 1].id
                else:
                    session.status = WorkflowStatus.COMPLETE

        session.updated_at = self._now()
        return session

    def fail_step(self, session_id: str, step_id: str, reason: str) -> WorkflowSession:
        session = self.get(session_id)
        session.status = WorkflowStatus.FAILED
        session.context["last_error"] = reason
        session.updated_at = self._now()
        return session

    def set_context(self, session_id: str, patch: dict[str, Any]) -> WorkflowSession:
        session = self.get(session_id)
        session.context.update(patch)
        session.updated_at = self._now()
        return session

    def cancel(self, session_id: str) -> WorkflowSession:
        session = self.get(session_id)
        session.status = WorkflowStatus.CANCELLED
        session.updated_at = self._now()
        return session


workflow_state_service = WorkflowStateService()
