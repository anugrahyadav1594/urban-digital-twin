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

import geoalchemy2.elements
if not hasattr(geoalchemy2.elements, "_patched_wkb_init"):
    _orig_wkb_init = geoalchemy2.elements.WKBElement.__init__

    def _patched_wkb_init(self, data, srid=-1, extended=None):
        if isinstance(data, str) and ("SRID=" in data or any(data.startswith(k) for k in ("POINT", "LINESTRING", "POLYGON", "MULTI"))):
            from shapely.wkt import loads as wkt_loads
            from shapely.wkb import dumps as wkb_dumps
            if "SRID=" in data:
                parts = data.split(";", 1)
                try:
                    srid = int(parts[0].replace("SRID=", ""))
                except Exception:
                    pass
                geom = wkt_loads(parts[1])
            else:
                geom = wkt_loads(data)
            data = wkb_dumps(geom, hex=True, srid=srid if srid != -1 else 4326)
        _orig_wkb_init(self, data, srid=srid, extended=extended)

    geoalchemy2.elements.WKBElement.__init__ = _patched_wkb_init
    geoalchemy2.elements._patched_wkb_init = True



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
