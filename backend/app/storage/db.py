"""SQLAlchemy engine and session factory. ARCHITECTURE §6.

One pooled engine per process. Sessions are short-lived and always closed.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..core.config import get_settings

log = logging.getLogger(__name__)

_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Lazily create the pooled engine."""
    global _engine
    if _engine is None:
        s = get_settings()
        _engine = create_engine(
            s.database_url,
            pool_pre_ping=True,          # drop dead connections instead of failing
            pool_size=s.db_pool_size,
            max_overflow=s.db_max_overflow,
            echo=s.db_echo,
            future=True,
        )

        @event.listens_for(_engine, "connect")
        def _set_timeout(dbapi_conn, _record):  # pragma: no cover - driver hook
            """Bound every statement so a runaway query cannot pin a worker."""
            with dbapi_conn.cursor() as cur:
                cur.execute(
                    f"SET statement_timeout = {s.sql_statement_timeout_ms}"
                )

        log.info("database engine created for %s", s.database_url_safe)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(
            bind=get_engine(), autocommit=False, autoflush=False,
            expire_on_commit=False, future=True,
        )
    return _SessionFactory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope. Commits on success, rolls back on any exception."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency. Read-only by default; callers commit explicitly."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def check_connection() -> dict[str, object]:
    """Health probe: verifies connectivity, PostGIS and the expected tables."""
    s = get_settings()
    out: dict[str, object] = {
        "connected": False, "postgis": None, "database": s.database_url_safe,
        "tables_present": 0, "missing_tables": [], "error": None,
    }
    expected = [
        "roads", "buildings", "facilities", "land_parcels", "population_zones",
        "administrative_areas", "planning_constraints", "water_bodies",
        "scenarios", "scenario_changes", "analysis_results",
    ]
    try:
        with get_engine().connect() as conn:
            out["postgis"] = conn.execute(
                text("SELECT PostGIS_Version();")
            ).scalar_one()
            rows = conn.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public'"
            )).scalars().all()
            present = set(rows)
            out["connected"] = True
            out["tables_present"] = len(present & set(expected))
            out["missing_tables"] = sorted(set(expected) - present)
    except Exception as exc:  # pragma: no cover - environment dependent
        out["error"] = str(exc)
    return out
