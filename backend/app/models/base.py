"""Declarative base and shared column helpers. ARCHITECTURE §6."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry
from geoalchemy2.shape import to_shape
from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

STORAGE_SRID = 4326


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    def shapely(self) -> Any:
        """Geometry column as a shapely object in EPSG:4326."""
        geom = getattr(self, "geometry", None)
        return None if geom is None else to_shape(geom)

    def as_dict(self, exclude_geometry: bool = True) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for col in self.__table__.columns:
            if exclude_geometry and isinstance(col.type, Geometry):
                continue
            val = getattr(self, col.name)
            out[col.name] = val.isoformat() if isinstance(val, datetime) else val
        return out


class TimestampMixin:
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
