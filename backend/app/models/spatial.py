"""ORM models mapped to the existing NAGAR-X PostGIS schema (db/schema.sql).

Column names mirror the live database exactly - height_m, slope_deg,
speed_limit, service_radius_m - so no migration is required. Translation to
the engine domain records (§9) happens in repositories/mappers.py.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String,
    Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import STORAGE_SRID, Base, TimestampMixin


class DatasetMetadata(Base, TimestampMixin):
    __tablename__ = "dataset_metadata"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    license: Mapped[str | None] = mapped_column(String(255))
    download_date: Mapped[date | None] = mapped_column(Date)
    resolution: Mapped[str | None] = mapped_column(String(100))
    crs: Mapped[str | None] = mapped_column(String(50))
    confidence: Mapped[str | None] = mapped_column(String(50))


class AdministrativeArea(Base, TimestampMixin):
    __tablename__ = "administrative_areas"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str | None] = mapped_column(String(100))
    population: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str | None] = mapped_column(String(255))
    geometry: Mapped[Any] = mapped_column(
        Geometry("MULTIPOLYGON", srid=STORAGE_SRID), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class Road(Base, TimestampMixin):
    __tablename__ = "roads"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    road_class: Mapped[str | None] = mapped_column(String(100))
    lanes: Mapped[int | None] = mapped_column(Integer)
    width_m: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    speed_limit: Mapped[int | None] = mapped_column(Integer)
    capacity: Mapped[int | None] = mapped_column(Integer)
    surface: Mapped[str | None] = mapped_column(String(50))
    oneway: Mapped[bool | None] = mapped_column(Boolean)
    source: Mapped[str | None] = mapped_column(String(255))
    geometry: Mapped[Any] = mapped_column(
        Geometry("MULTILINESTRING", srid=STORAGE_SRID), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class RoadNode(Base, TimestampMixin):
    __tablename__ = "road_nodes"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    geometry: Mapped[Any] = mapped_column(
        Geometry("POINT", srid=STORAGE_SRID), nullable=False
    )


class RoadEdge(Base, TimestampMixin):
    __tablename__ = "road_edges"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_node: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("road_nodes.id", ondelete="CASCADE")
    )
    target_node: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("road_nodes.id", ondelete="CASCADE")
    )
    length_m: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    travel_time_sec: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    road_class: Mapped[str | None] = mapped_column(String(100))
    geometry: Mapped[Any] = mapped_column(
        Geometry("LINESTRING", srid=STORAGE_SRID), nullable=False
    )


class Building(Base, TimestampMixin):
    __tablename__ = "buildings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    height_m: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    floors: Mapped[int | None] = mapped_column(Integer)
    building_type: Mapped[str | None] = mapped_column(String(100))
    land_use: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    population_estimate: Mapped[int | None] = mapped_column(Integer)
    risk_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    source: Mapped[str | None] = mapped_column(String(255))
    geometry: Mapped[Any] = mapped_column(
        Geometry("MULTIPOLYGON", srid=STORAGE_SRID), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class Facility(Base, TimestampMixin):
    __tablename__ = "facilities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    capacity: Mapped[int | None] = mapped_column(Integer)
    service_radius_m: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    source: Mapped[str | None] = mapped_column(String(255))
    # Schema uses the generic Geometry type: points AND polygons both occur.
    geometry: Mapped[Any] = mapped_column(
        Geometry("GEOMETRY", srid=STORAGE_SRID), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class PopulationZone(Base, TimestampMixin):
    __tablename__ = "population_zones"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    population: Mapped[int | None] = mapped_column(Integer)
    households: Mapped[int | None] = mapped_column(Integer)
    density_per_sqkm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    source: Mapped[str | None] = mapped_column(String(255))
    geometry: Mapped[Any] = mapped_column(
        Geometry("POLYGON", srid=STORAGE_SRID), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class LandParcel(Base, TimestampMixin):
    __tablename__ = "land_parcels"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    land_use: Mapped[str | None] = mapped_column(String(100))
    zoning: Mapped[str | None] = mapped_column(String(100))
    development_status: Mapped[str | None] = mapped_column(String(100))
    slope_deg: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    elevation_m: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    flood_risk: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    source: Mapped[str | None] = mapped_column(String(255))
    geometry: Mapped[Any] = mapped_column(
        Geometry("POLYGON", srid=STORAGE_SRID), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class WaterBody(Base, TimestampMixin):
    __tablename__ = "water_bodies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str | None] = mapped_column(String(100))
    seasonality: Mapped[str | None] = mapped_column(String(50))
    source: Mapped[str | None] = mapped_column(String(255))
    geometry: Mapped[Any] = mapped_column(
        Geometry("MULTIPOLYGON", srid=STORAGE_SRID), nullable=False
    )


class PlanningConstraint(Base, TimestampMixin):
    __tablename__ = "planning_constraints"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str | None] = mapped_column(String(50))
    source: Mapped[str | None] = mapped_column(String(255))
    geometry: Mapped[Any] = mapped_column(
        Geometry("MULTIPOLYGON", srid=STORAGE_SRID), nullable=False
    )


class Scenario(Base, TimestampMixin):
    __tablename__ = "scenarios"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    base_version: Mapped[str | None] = mapped_column(String(50))
    created_by: Mapped[str | None] = mapped_column(String(100))


class ScenarioChange(Base, TimestampMixin):
    __tablename__ = "scenario_changes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("scenarios.id", ondelete="CASCADE")
    )
    object_type: Mapped[str] = mapped_column(String(100), nullable=False)
    object_id: Mapped[int | None] = mapped_column(Integer)
    operation: Mapped[str] = mapped_column(String(50), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False)


class AnalysisResult(Base, TimestampMixin):
    __tablename__ = "analysis_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("scenarios.id", ondelete="CASCADE")
    )
    analysis_type: Mapped[str] = mapped_column(String(100), nullable=False)
    result_json: Mapped[dict] = mapped_column(JSONB, nullable=False)


class SpatialEntity(Base, TimestampMixin):
    __tablename__ = "spatial_entities"
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    table_name: Mapped[str | None] = mapped_column(String(100))
    record_id: Mapped[int | None] = mapped_column(Integer)


class EntityRelationship(Base, TimestampMixin):
    __tablename__ = "entity_relationships"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_entity: Mapped[str | None] = mapped_column(
        String(255), ForeignKey("spatial_entities.id", ondelete="CASCADE")
    )
    predicate: Mapped[str] = mapped_column(String(100), nullable=False)
    object_entity: Mapped[str | None] = mapped_column(
        String(255), ForeignKey("spatial_entities.id", ondelete="CASCADE")
    )
    distance_m: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
