"""FastAPI application. ARCHITECTURE §5.

Run from backend/:
    uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from .api.v1.router import api_router
from .core.config import get_settings
from .storage.db import check_connection

log = logging.getLogger("uvicorn.error")

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_settings()
    info = check_connection()
    log.info("database %s", info["database"])
    log.info("CRS storage EPSG:%s -> analysis EPSG:%s",
             cfg.storage_srid, cfg.analysis_srid)
    if not info["connected"]:
        log.error("DATABASE UNREACHABLE - data endpoints will return 503")
        log.error("run: python -m app.storage.doctor")
    elif info["missing_tables"]:
        log.warning("missing tables: %s", ", ".join(info["missing_tables"]))
    else:
        log.info("PostGIS %s | %d/11 core tables",
                 info["postgis"], info["tables_present"])
    yield


app = FastAPI(
    title="NAGAR-X Urban Digital Twin API",
    version="1.0.0",
    description="Planning, analysis and scenario endpoints over a PostGIS city model.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(OperationalError)
async def db_unavailable(request: Request, exc: OperationalError) -> JSONResponse:
    """A database outage is a dependency failure (503), not a server bug."""
    log.error("database unavailable on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=503,
        content={"error": "database unavailable", "path": request.url.path,
                 "hint": "run: python -m app.storage.doctor"},
    )


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "internal server error", "path": request.url.path,
                 "detail": type(exc).__name__},
    )


app.include_router(api_router, prefix=API_PREFIX)


@app.get("/", tags=["health"])
def root() -> dict[str, object]:
    return {
        "service": "NAGAR-X Urban Digital Twin API",
        "version": "1.0.0",
        "docs": "/docs",
        "apiBase": API_PREFIX,
        "endpoints": sorted(app.openapi().get("paths", {})),
    }
