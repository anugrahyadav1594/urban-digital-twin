"""Database bootstrap and health CLI. ARCHITECTURE §6.

Usage:
    python -m app.storage.bootstrap check      # connectivity + PostGIS + tables
    python -m app.storage.bootstrap schema     # apply db/schema.sql
    python -m app.storage.bootstrap counts     # row counts per table
"""
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

from ..core.config import get_settings
from .db import check_connection, get_engine, session_scope


def find_schema_sql() -> Path | None:
    """Locate db/schema.sql by walking up from this module.

    Uses is_file(), not exists(): Docker CREATES A DIRECTORY at a bind-mount
    source path that does not exist, so a missing schema.sql silently becomes
    an empty directory named schema.sql. exists() accepts it and read_text()
    then dies with IsADirectoryError.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "db" / "schema.sql"
        if cand.is_file():
            return cand
    return None


def _report_missing_schema() -> None:
    """Explain the two distinct ways schema.sql can be unusable."""
    here = Path(__file__).resolve()
    stray: list[Path] = []
    for parent in here.parents:
        cand = parent / "db" / "schema.sql"
        if cand.is_dir():
            stray.append(cand)
        if (parent / ".git").exists():
            break

    if stray:
        print("[ERROR] db/schema.sql is a DIRECTORY, not a file:")
        for d in stray:
            contents = list(d.iterdir()) if d.is_dir() else []
            print(f"        {d}  ({len(contents)} entries)")
        print()
        print("        Docker created it. A bind mount whose source file does")
        print("        not exist is materialised as an empty directory.")
        print()
        print("        Fix:")
        print("          docker compose down")
        for d in stray:
            print(f"          rmdir {d}")
        print("          # restore the real schema.sql, then:")
        print("          docker compose up -d db")
    else:
        print("[ERROR] db/schema.sql not found")
        print("        Expected at <repo-root>/db/schema.sql")
    raise SystemExit(1)


def apply_schema() -> None:
    path = find_schema_sql()
    if path is None:
        _report_missing_schema()
        return
    sql = path.read_text(encoding="utf-8")
    if not sql.strip():
        print(f"[ERROR] {path} is empty")
        raise SystemExit(1)
    with get_engine().begin() as conn:
        conn.execute(text(sql))
    print(f"[OK] schema applied from {path}")


def check() -> None:
    s = get_settings()
    info = check_connection()
    print(f"database        : {info['database']}")
    print(f"analysis SRID   : EPSG:{s.analysis_srid} (storage EPSG:{s.storage_srid})")
    if not info["connected"]:
        print(f"[FAIL] not connected: {info['error']}")
        raise SystemExit(1)
    print(f"[OK] connected  : PostGIS {info['postgis']}")
    print(f"core tables     : {info['tables_present']}/11 present")
    if info["missing_tables"]:
        print(f"[WARN] missing  : {', '.join(info['missing_tables'])}")
        print("       run: python -m app.storage.bootstrap schema")


def counts() -> None:
    from ..repositories import SpatialRepository
    with session_scope() as sess:
        for k, v in SpatialRepository(sess).counts().items():
            print(f"  {k:24s} {v:>8d}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    {"check": check, "schema": apply_schema, "counts": counts}.get(
        cmd, check
    )()
