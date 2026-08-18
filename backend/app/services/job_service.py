"""In-memory and persistent Job status tracking service. ARCHITECTURE §18."""
from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional


class JobService:
    _jobs: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def create_job(cls, title: str, kind: str, stages: List[Dict[str, Any]]) -> Dict[str, Any]:
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        now = int(time.time() * 1000)
        formatted_stages = [
            {"key": s.get("key", f"stg_{i}"), "label": s.get("label", f"Stage {i+1}"), "state": "pending"}
            for i, s in enumerate(stages)
        ]
        if formatted_stages:
            formatted_stages[0]["state"] = "running"

        job = {
            "id": job_id,
            "title": title,
            "kind": kind,
            "progress": 5 if stages else 100,
            "state": "running",
            "stages": formatted_stages,
            "result_id": None,
            "error": None,
            "startedAt": now,
        }
        cls._jobs[job_id] = job
        return job

    @classmethod
    def get_job(cls, job_id: str) -> Optional[Dict[str, Any]]:
        return cls._jobs.get(job_id)

    @classmethod
    def update_job(
        cls,
        job_id: str,
        state: Optional[str] = None,
        progress: Optional[int] = None,
        stages: Optional[List[Dict[str, Any]]] = None,
        result_id: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        job = cls._jobs.get(job_id)
        if not job:
            return None
        if state is not None:
            job["state"] = state
        if progress is not None:
            job["progress"] = progress
        if stages is not None:
            job["stages"] = stages
        if result_id is not None:
            job["result_id"] = str(result_id)
        if error is not None:
            job["error"] = error
            job["state"] = "failed"
        return job
