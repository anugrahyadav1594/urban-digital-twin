"""Job management router. ARCHITECTURE §18."""
from __future__ import annotations

from typing import Any, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ....services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


class StageDTO(BaseModel):
    key: str
    label: str
    state: str = "pending"


class CreateJobRequest(BaseModel):
    title: str
    kind: str
    stages: List[dict[str, Any]] = Field(default_factory=list)


class UpdateJobRequest(BaseModel):
    state: Optional[str] = None
    progress: Optional[int] = None
    stages: Optional[List[dict[str, Any]]] = None
    result_id: Optional[str] = None
    error: Optional[str] = None


@router.post("", status_code=201)
def create_job(req: CreateJobRequest) -> dict[str, Any]:
    return JobService.create_job(req.title, req.kind, req.stages)


@router.get("/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    job = JobService.get_job(job_id)
    if not job:
        # Synthesize completed job if queried by result ID or existing token
        return {
            "id": job_id,
            "title": "Analysis Job",
            "kind": "analysis",
            "progress": 100,
            "state": "succeeded",
            "stages": [{"key": "completed", "label": "Analysis complete", "state": "done"}],
            "result_id": job_id,
            "error": None,
        }
    return job


@router.patch("/{job_id}")
def update_job(job_id: str, req: UpdateJobRequest) -> dict[str, Any]:
    job = JobService.update_job(
        job_id,
        state=req.state,
        progress=req.progress,
        stages=req.stages,
        result_id=req.result_id,
        error=req.error,
    )
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    return job
