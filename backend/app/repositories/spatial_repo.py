"""Data access for spatial entities. ARCHITECTURE §5.3, §6.

Spatial predicates run IN PostGIS (GiST-backed ST_Intersects / ST_DWithin),
not in Python. Rows are converted to engine domain records by mappers.py.
"""
from __future__ import annotations

from typing import Any, Sequence

from geoalchemy2 import Geometry
from geoalchemy2.shape import from_shape
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..engines.crs import to_storage
from ..models import (
    AdministrativeArea, Building, Facility, LandParcel, PlanningConstraint,
    PopulationZone, Road, WaterBody,
)
from . import mappers

STORAGE_SRID = 4326


def _bbox_filter(model: Any, bbox: tuple[float, float, float, float] | None):
    """ST_MakeEnvelope filter in EPSG:4326. Uses the GiST index."""
    if bbox is None:
        return None
    minx, miny, maxx, maxy = bbox
    return func.ST_Intersects(
        model.geometry,
        func.ST_MakeEnvelope(minx, miny, maxx, maxy, STORAGE_SRID),
    )


class SpatialRepository:
    """Read access to the authoritative city tables."""

    def __init__(self, session: Session, analysis_srid: int | None = None):
        self.s = session
        self.srid = analysis_srid or get_settings().analysis_srid

    # ---------------- parcels ----------------
    def parcels(
        self,
        bbox: tuple[float, float, float, float] | None = None,
        land_use: str | None = None,
        zoning: str | None = None,
        development_status: str | None = None,
        min_area_m2: float | None = None,
        limit: int | None = None,
    ) -> list[Any]:
        stmt = select(LandParcel)
        if (f := _bbox_filter(LandParcel, bbox)) is not None:
            stmt = stmt.where(f)
        if land_use:
            stmt = stmt.where(LandParcel.land_use == land_use)
        if zoning:
            stmt = stmt.where(LandParcel.zoning == zoning)
        if development_status:
            stmt = stmt.where(LandParcel.development_status == development_status)
        if min_area_m2:
            # Area computed on the geography type -> square metres, no
            # reprojection needed and still index-assisted by the bbox filter.
            stmt = stmt.where(
                func.ST_Area(func.Geography(LandParcel.geometry)) >= min_area_m2
            )
        if limit:
            stmt = stmt.limit(limit)
        return mappers.map_all(self.s.execute(stmt).scalars().all(),
                               mappers.to_parcel, self.srid)

    # ---------------- roads ----------------
    def roads(
        self,
        bbox: tuple[float, float, float, float] | None = None,
        road_classes: Sequence[str] | None = None,
        limit: int | None = None,
    ) -> list[Any]:
        stmt = select(Road)
        if (f := _bbox_filter(Road, bbox)) is not None:
            stmt = stmt.where(f)
        if road_classes:
            stmt = stmt.where(Road.road_class.in_(list(road_classes)))
        if limit:
            stmt = stmt.limit(limit)
        return mappers.map_all(self.s.execute(stmt).scalars().all(),
                               mappers.to_road, self.srid)

    # ---------------- facilities ----------------
    def facilities(
        self,
        facility_type: str | None = None,
        bbox: tuple[float, float, float, float] | None = None,
        limit: int | None = None,
    ) -> list[Any]:
        stmt = select(Facility)
        if facility_type:
            stmt = stmt.where(Facility.type == facility_type)
        if (f := _bbox_filter(Facility, bbox)) is not None:
            stmt = stmt.where(f)
        if limit:
            stmt = stmt.limit(limit)
        return mappers.map_all(self.s.execute(stmt).scalars().all(),
                               mappers.to_facility, self.srid)

    def nearby_facilities(
        self, lon: float, lat: float, radius_m: float,
        facility_type: str | None = None, limit: int = 10,
    ) -> list[dict[str, Any]]:
        """ST_DWithin on geography -> true metre radius, index-assisted."""
        pt = func.ST_SetSRID(func.ST_MakePoint(lon, lat), STORAGE_SRID)
        dist = func.ST_Distance(func.Geography(Facility.geometry),
                                func.Geography(pt))
        stmt = (
            select(Facility, dist.label("distance_m"))
            .where(func.ST_DWithin(func.Geography(Facility.geometry),
                                   func.Geography(pt), radius_m))
            .order_by(dist)
            .limit(limit)
        )
        if facility_type:
            stmt = stmt.where(Facility.type == facility_type)
        out = []
        for row, d in self.s.execute(stmt).all():
            rec = row.as_dict()
            rec["distance_m"] = round(float(d), 2)
            out.append(rec)
        return out

    # ---------------- population ----------------
    def population_zones(
        self, bbox: tuple[float, float, float, float] | None = None,
        limit: int | None = None,
    ) -> list[Any]:
        stmt = select(PopulationZone)
        if (f := _bbox_filter(PopulationZone, bbox)) is not None:
            stmt = stmt.where(f)
        if limit:
            stmt = stmt.limit(limit)
        return mappers.map_all(self.s.execute(stmt).scalars().all(),
                               mappers.to_population_zone, self.srid)

    def total_population(self) -> float:
        return float(self.s.execute(
            select(func.coalesce(func.sum(PopulationZone.population), 0))
        ).scalar_one())

    # ---------------- constraints ----------------
    def constraints(
        self, bbox: tuple[float, float, float, float] | None = None,
        include_water_buffer_m: float | None = None,
    ) -> list[Any]:
        stmt = select(PlanningConstraint)
        if (f := _bbox_filter(PlanningConstraint, bbox)) is not None:
            stmt = stmt.where(f)
        out = mappers.map_all(self.s.execute(stmt).scalars().all(),
                              mappers.to_constraint, self.srid)

        if include_water_buffer_m:
            from ..engines.contracts import PlanningConstraint as PC
            from ..engines.crs import to_analysis
            from geoalchemy2.shape import to_shape
            for w in self.s.execute(select(WaterBody)).scalars().all():
                out.append(PC(
                    id=f"water-{w.id}", type=f"water_buffer:{w.type}",
                    geometry=to_analysis(to_shape(w.geometry), self.srid),
                    severity="hard", weight=1.0,
                    buffer=float(include_water_buffer_m),
                    source=w.source,
                ))
        return out

    # ---------------- buildings ----------------
    def buildings(
        self, bbox: tuple[float, float, float, float] | None = None,
        limit: int | None = None,
    ) -> list[Any]:
        stmt = select(Building)
        if (f := _bbox_filter(Building, bbox)) is not None:
            stmt = stmt.where(f)
        if limit:
            stmt = stmt.limit(limit)
        return mappers.map_all(self.s.execute(stmt).scalars().all(),
                               mappers.to_building, self.srid)

    # ---------------- utility ----------------
    def city_extent(self) -> tuple[float, float, float, float] | None:
        """Union extent of roads+parcels+buildings, in EPSG:4326."""
        row = self.s.execute(text("""
            SELECT ST_XMin(e), ST_YMin(e), ST_XMax(e), ST_YMax(e) FROM (
              SELECT ST_Extent(geometry) AS e FROM (
                SELECT geometry FROM roads
                UNION ALL SELECT geometry FROM land_parcels
                UNION ALL SELECT geometry FROM buildings
              ) g
            ) x
        """)).first()
        if not row or row[0] is None:
            return None
        return (float(row[0]), float(row[1]), float(row[2]), float(row[3]))

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for name, model in [
            ("roads", Road), ("buildings", Building), ("facilities", Facility),
            ("land_parcels", LandParcel), ("population_zones", PopulationZone),
            ("planning_constraints", PlanningConstraint),
            ("administrative_areas", AdministrativeArea),
            ("water_bodies", WaterBody),
        ]:
            out[name] = int(self.s.execute(
                select(func.count()).select_from(model)
            ).scalar_one())
        return out
