"""Validator helpers for backend workflow step prerequisites and constraint rules."""
from __future__ import annotations

from .exceptions import WorkflowPrerequisiteError, WorkflowValidationError
from .schemas import WorkflowSession


def validate_prerequisite(session: WorkflowSession, required_step: str, current_step: str) -> None:
    """Verify that a prerequisite step has completed."""
    if required_step not in session.completed_steps:
        raise WorkflowPrerequisiteError(required_step=required_step, current_step=current_step)


def validate_constraint_pass(session: WorkflowSession, current_step: str = "commit") -> None:
    """Verify that constraint validation status is PASS before allowing scenario commits."""
    if session.validation_status != "PASS":
        raise WorkflowValidationError(
            message=f"Cannot execute commit. Constraint validation status is '{session.validation_status}'. "
                    "Constraint validation must PASS before committing scenario changes.",
            step=current_step,
            details=[f"Validation status: {session.validation_status}"]
        )


def validate_result_exists(session: WorkflowSession, action_name: str) -> str:
    """Verify that a result ID exists in context."""
    if not session.result_ids:
        raise WorkflowValidationError(
            message=f"Cannot execute '{action_name}'. No engine results are recorded in this workflow session.",
            step=session.current_step
        )
    return session.result_ids[-1]
