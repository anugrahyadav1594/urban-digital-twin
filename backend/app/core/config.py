"""Typed settings loaded from environment. ARCHITECTURE §5, §6.5.

Reads the same POSTGIS_* variables the existing db/db_config.py uses, so the
ETL scripts and this backend point at one database without reconfiguration.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str:
    """Locate .env by walking up from this file to the repo root.

    A plain env_file=".env" resolves against the CURRENT WORKING DIRECTORY,
    so `cd backend && python -m ...` silently ignores the repo-root .env and
    falls back to defaults - including the hardcoded password. Anchoring the
    search to this module makes configuration independent of where you stand.
    Precedence is unchanged: real environment variables still win.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / ".env"
        if candidate.is_file():
            return str(candidate)
        if (parent / ".git").exists():        # stop at the repo root
            break
    return ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_find_env_file(), env_file_encoding="utf-8", extra="ignore"
    )

    # --- Database (names match the existing db/db_config.py) ---
    postgis_host: str = Field("localhost", alias="POSTGIS_HOST")
    postgis_port: int = Field(5432, alias="POSTGIS_PORT")
    postgis_db: str = Field("nagar_x_db", alias="POSTGIS_DB")
    postgis_user: str = Field("postgres", alias="POSTGIS_USER")
    postgis_password: str = Field("2415", alias="POSTGIS_PASSWORD")

    # --- CRS policy (§6.5) ---
    # Storage is always EPSG:4326. The analysis CRS must be projected.
    # Pilot zone is Adivali-devad / NAINA, Navi Mumbai -> UTM 43N.
    storage_srid: int = Field(4326, alias="STORAGE_SRID")
    analysis_srid: int = Field(32643, alias="ANALYSIS_SRID")

    # --- Versioning (§25) ---
    dataset_version: int = Field(1, alias="ACTIVE_DATASET_VERSION")

    # --- Pool tuning ---
    db_pool_size: int = Field(5, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(10, alias="DB_MAX_OVERFLOW")
    db_echo: bool = Field(False, alias="DB_ECHO")

    sql_statement_timeout_ms: int = Field(30_000, alias="SQL_STATEMENT_TIMEOUT_MS")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgis_user}:{self.postgis_password}"
            f"@{self.postgis_host}:{self.postgis_port}/{self.postgis_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url_safe(self) -> str:
        """Connection string with the password masked, safe to log."""
        return (
            f"postgresql://{self.postgis_user}:***"
            f"@{self.postgis_host}:{self.postgis_port}/{self.postgis_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
