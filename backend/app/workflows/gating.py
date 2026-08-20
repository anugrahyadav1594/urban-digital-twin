"""Step gating and prerequisite validation rules for backend workflows."""
from __future__ import annotations

from typing import Any, Sequence
from fastapi import HTTPException
from .schemas import WorkflowSession


class WorkflowValidationError(HTTPException):
    def __init__(self, code: str, message: str, step: str, details: list[Any] | None = None):
        super().__init__(
            status_code=422,
            detail={
                "error": {
                    "code": code,
                    "message": message,
                    "step": step,
                    "details": details or []
                }
            }
        )


def validate_step_prerequisite(session: WorkflowSession, required_step: str, action_name: str) -> None:
    """Verify that a prerequisite workflow step has completed."""
    if required_step not in session.completed_steps:
        raise WorkflowValidationError(
            code="PREREQUISITE_STEP_MISSING",
            message=f"Cannot execute '{action_name}'. Step '{required_step}' must be completed first.",
            step=session.current_step,
            details=[f"Required step: {required_step}", f"Completed steps: {session.completed_steps}"]
        )


def validate_constraint_pass(session: WorkflowSession, action_name: str) -> None:
    """Verify that constraint validation passed before allowing scenario commits."""
    if session.validation_status != "PASS":
        raise WorkflowValidationError(
            code="CONSTRAINT_VALIDATION_FAILED",
            message=f"Cannot execute '{action_name}'. Constraint validation status is '{session.validation_status}'. "
                    "Constraint validation must PASS before committing scenario changes.",
            step=session.current_step,
            details=[f"Validation status: {session.validation_status}"]
        )


def validate_result_exists(session: WorkflowSession, action_name: str) -> str:
    """Verify that a valid result ID exists in the session context."""
    if not session.result_ids:
        raise WorkflowValidationError(
            code="RESULT_NOT_FOUND",
            message=f"Cannot execute '{action_name}'. No engine results are recorded in this workflow session.",
            step=session.current_step
        )
    return session.result_ids[-1]
