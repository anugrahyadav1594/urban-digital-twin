"""Stored results. ARCHITECTURE §5 /results, §22."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ...dto import analysis_dto
from ...deps import Results

router = APIRouter(tags=["results"])


@router.get("/results/{result_id}")
def get_result(result_id: int, repo: Results) -> dict[str, Any]:
    row = repo.get(result_id)
    if row is None:
        raise HTTPException(404, f"result {result_id} not found")
    payload = row["result"]
    payload["result_id"] = row["id"]
    return analysis_dto(payload, payload.get("result_type", "Result"))
