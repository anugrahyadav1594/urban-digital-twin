"""Liveness and readiness. ARCHITECTURE §5."""
from __future__ import annotations

from fastapi import APIRouter, Response, status

from ....core.config import get_settings
from ....storage.db import check_connection

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(response: Response) -> dict[str, object]:
    info = check_connection()
    cfg = get_settings()
    ok = info["connected"] and not info["missing_tables"]
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "ready": ok,
        "database": info["database"],
        "postgis": info["postgis"],
        "tablesPresent": info["tables_present"],
        "missingTables": info["missing_tables"],
        "analysisSrid": cfg.analysis_srid,
        "storageSrid": cfg.storage_srid,
    }
