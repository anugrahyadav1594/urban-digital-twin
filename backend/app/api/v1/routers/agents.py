"""Agent endpoints. ARCHITECTURE §19-21.

The multi-agent runtime is not implemented; these endpoints report that
honestly rather than returning fabricated reasoning traces.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/agents", tags=["agents"])


class AskRequest(BaseModel):
    question: str
    scenario_id: int | None = None


@router.get("/status")
def status() -> dict[str, Any]:
    return {"implemented": False,
            "reason": "multi-agent runtime not built (ARCHITECTURE 19-21)",
            "available_tools": []}


@router.post("/ask", status_code=501)
def ask(req: AskRequest) -> dict[str, Any]:
    return {"error": "not implemented",
            "detail": "The agent orchestrator is scaffolded but empty. "
                      "Use /planning and /analysis directly.",
            "question": req.question}
