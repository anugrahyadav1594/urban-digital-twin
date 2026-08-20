"""Structured workflow exceptions and HTTP error mappings."""
from __future__ import annotations

from typing import Any
from fastapi import HTTPException


class WorkflowError(HTTPException):
    def __init__(
        self,
        code: str,
        message: str,
        step: str | None = None,
        status_code: int = 422,
        details: list[Any] | None = None
    ):
        super().__init__(
            status_code=status_code,
            detail={
                "error": {
                    "code": code,
                    "message": message,
                    "step": step,
                    "details": details or []
                }
            }
        )
        self.code = code
        self.message = message
        self.step = step


class WorkflowNotFoundError(WorkflowError):
    def __init__(self, session_id: str, step: str | None = None):
        super().__init__(
            code="WORKFLOW_SESSION_NOT_FOUND",
            message=f"Workflow session '{session_id}' not found.",
            step=step,
            status_code=404
        )


class WorkflowTransitionError(WorkflowError):
    def __init__(self, message: str, step: str | None = None, details: list[Any] | None = None):
        super().__init__(
            code="INVALID_WORKFLOW_TRANSITION",
            message=message,
            step=step,
            status_code=422,
            details=details
        )


class WorkflowPrerequisiteError(WorkflowError):
    def __init__(self, required_step: str, current_step: str | None = None):
        super().__init__(
            code="STEP_PREREQUISITE_FAILED",
            message=f"Prerequisite step '{required_step}' must be completed before advancing to step '{current_step}'.",
            step=current_step,
            status_code=422,
            details=[f"Required step: {required_step}"]
        )


class WorkflowValidationError(WorkflowError):
    def __init__(self, message: str, step: str = "validate", details: list[Any] | None = None):
        super().__init__(
            code="CONSTRAINT_VALIDATION_FAILED",
            message=message,
            step=step,
            status_code=422,
            details=details
        )


class ScenarioCommitError(WorkflowError):
    def __init__(self, message: str, step: str = "commit", details: list[Any] | None = None):
        super().__init__(
            code="SCENARIO_COMMIT_FAILED",
            message=message,
            step=step,
            status_code=422,
            details=details
        )


class SimulationError(WorkflowError):
    def __init__(self, message: str, step: str = "simulate"):
        super().__init__(
            code="SIMULATION_FAILED",
            message=message,
            step=step,
            status_code=500
        )


class RoutingError(WorkflowError):
    def __init__(self, message: str, step: str = "reroute"):
        super().__init__(
            code="ROUTING_FAILED",
            message=message,
            step=step,
            status_code=422
        )


class ComparisonError(WorkflowError):
    def __init__(self, message: str, step: str = "compare"):
        super().__init__(
            code="COMPARISON_FAILED",
            message=message,
            step=step,
            status_code=422
        )
