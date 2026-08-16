"""Shared fixtures. Integration tests require a live PostGIS."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.storage.db import check_connection, session_scope  # noqa: E402

DB_UP = check_connection()["connected"]
requires_db = pytest.mark.skipif(not DB_UP, reason="PostGIS not reachable")


@pytest.fixture
def session():
    with session_scope() as s:
        yield s
