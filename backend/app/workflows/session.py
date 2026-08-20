"""Session state management for workflow orchestration."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from .schemas import ValidationStatus, WorkflowId, WorkflowSession


class SessionStore:
    def __init__(self):
        self._sessions: dict[str, WorkflowSession] = {}

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create(
        self,
        workflow_id: WorkflowId,
        scenario_id: int | str,
        initial_context: dict[str, Any] | None = None
    ) -> WorkflowSession:
        sid = f"wf_sess_{uuid.uuid4().hex[:12]}"

        initial_steps = {
            "plan": "requirement",
            "stress": "scenario",
            "improve": "score",
            "compare": "variants",
            "explain": "recommendation"
        }

        session = WorkflowSession(
            session_id=sid,
            workflow_id=workflow_id,
            scenario_id=scenario_id,
            current_step=initial_steps.get(workflow_id, "start"),
            completed_steps=[],
            validation_status="PENDING",
            result_ids=[],
            context_data=initial_context or {},
            created_at=self._now(),
            updated_at=self._now()
        )
        self._sessions[sid] = session
        return session

    def get(self, session_id: str) -> WorkflowSession | None:
        return self._sessions.get(session_id)

    def update(
        self,
        session_id: str,
        current_step: str | None = None,
        completed_step: str | None = None,
        validation_status: ValidationStatus | None = None,
        add_result_id: str | None = None,
        context_patch: dict[str, Any] | None = None
    ) -> WorkflowSession | None:
        session = self.get(session_id)
        if not session:
            return None

        if current_step:
            session.current_step = current_step

        if completed_step and completed_step not in session.completed_steps:
            session.completed_steps.append(completed_step)

        if validation_status:
            session.validation_status = validation_status

        if add_result_id and add_result_id not in session.result_ids:
            session.result_ids.append(add_result_id)

        if context_patch:
            session.context_data.update(context_patch)

        session.updated_at = self._now()
        return session


# Global thread-safe session store instance
session_store = SessionStore()
