"""Shared domain types and result contracts for all engines.

ARCHITECTURE refs: §9 (data model), §22 (results), §25 (reproducibility).

Engines are pure functions of versioned inputs. They accept plain domain
records (not ORM objects, not GeoDataFrames) so they stay testable and
independent of the persistence layer.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

# --------------------------------------------------------------------------
# Enumerations
# --------------------------------------------------------------------------


class Operation(str, Enum):
    ADD = "add"
    MODIFY = "modify"
    DELETE = "delete"


class EntityType(str, Enum):
    BUILDING = "building"
    ROAD = "road"
    PARCEL = "parcel"
    FACILITY = "facility"
    LANDUSE_ZONE = "landuse_zone"
    POPULATION_ZONE = "population_zone"
    INFRASTRUCTURE_ASSET = "infrastructure_asset"
    CONSTRAINT = "constraint"


class Severity(str, Enum):
    """Constraint severity. HARD disqualifies, SOFT penalises. §9.6."""

    HARD = "hard"
    SOFT = "soft"


class DevelopmentStatus(str, Enum):
    VACANT = "vacant"
    BUILT = "built"
    UNDER_DEVELOPMENT = "under_development"
    PROTECTED = "protected"


# --------------------------------------------------------------------------
# Provenance / results  (§22, §25)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Provenance:
    """Identifies exactly how a result was produced.

    The reproducibility tuple of §25 is
    ``dataset_version + scenario_version + algorithm_version + parameters``.
    """

    dataset_version: int
    algorithm: str
    algorithm_version: str
    scenario_version: int | None = None
    scenario_id: str | None = None
    scoring_profile_version: str | None = None
    cost_profile_version: str | None = None
    analysis_srid: int = 32644
    parameters: Mapping[str, Any] = field(default_factory=dict)
    assumptions: Sequence[str] = field(default_factory=tuple)
    source_references: Sequence[str] = field(default_factory=tuple)

    def parameter_hash(self) -> str:
        """Stable hash of the reproducibility tuple; used as an idempotency key."""
        payload = {
            "dataset_version": self.dataset_version,
            "scenario_version": self.scenario_version,
            "algorithm": self.algorithm,
            "algorithm_version": self.algorithm_version,
            "scoring_profile_version": self.scoring_profile_version,
            "cost_profile_version": self.cost_profile_version,
            "analysis_srid": self.analysis_srid,
            "parameters": _canonical(self.parameters),
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()

    def with_assumptions(self, *extra: str) -> "Provenance":
        """Return a copy with additional assumptions appended (§22)."""
        import dataclasses
        merged = tuple(list(self.assumptions) + [e for e in extra if e])
        return dataclasses.replace(self, assumptions=merged)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["assumptions"] = list(self.assumptions)
        d["source_references"] = list(self.source_references)
        d["parameters"] = _canonical(self.parameters)
        d["parameter_hash"] = self.parameter_hash()
        return d


@dataclass(frozen=True)
class Metric:
    """A single named quantity. Units are mandatory (§22)."""

    name: str
    value: float | int | None
    unit: str
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "confidence": self.confidence,
        }


@dataclass
class EngineResult:
    """Uniform envelope returned by every engine. Persisted verbatim (§22)."""

    result_type: str
    provenance: Provenance
    metrics: list[Metric] = field(default_factory=list)
    records: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def metric(self, name: str) -> Metric | None:
        return next((m for m in self.metrics if m.name == name), None)

    def value(self, name: str, default: float | None = None) -> float | None:
        m = self.metric(name)
        return default if m is None or m.value is None else float(m.value)

    def add(self, name: str, value: float | int | None, unit: str,
            confidence: float | None = None) -> None:
        self.metrics.append(Metric(name, value, unit, confidence))

    def to_dict(self) -> dict[str, Any]:
        """Machine-readable form for the API, the frontend and the tool layer."""
        return {
            "result_type": self.result_type,
            "timestamp": self.timestamp,
            "provenance": self.provenance.to_dict(),
            "metrics": [m.to_dict() for m in self.metrics],
            "records": self.records,
            "artifacts": self.artifacts,
            "warnings": self.warnings,
        }

    def to_json(self, indent: int | None = None) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)


def _canonical(obj: Any) -> Any:
    """Recursively convert to JSON-stable primitives for hashing."""
    if isinstance(obj, Mapping):
        return {str(k): _canonical(obj[k]) for k in sorted(obj, key=str)}
    if isinstance(obj, (list, tuple)):
        return [_canonical(v) for v in obj]
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, float):
        return round(obj, 10)
    return obj


# --------------------------------------------------------------------------
# Domain records  (§9)
# --------------------------------------------------------------------------


@dataclass
class Parcel:
    """§9.3 Land parcel."""

    id: str
    geometry: Any                      # shapely geometry, analysis CRS
    area: float | None = None          # m^2
    land_use: str | None = None
    zoning: str | None = None
    development_status: str = DevelopmentStatus.VACANT.value
    slope: float | None = None         # degrees
    elevation: float | None = None     # m
    flood_risk: float | None = None    # 0..1 exposure index
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Building:
    """§9.1 Building."""

    id: str
    geometry: Any
    height: float | None = None
    floors: int | None = None
    building_type: str | None = None
    land_use: str | None = None
    confidence: float | None = None
    population_estimate: float | None = None
    risk_attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Road:
    """§9.2 Road segment."""

    id: str
    geometry: Any                      # shapely LineString, analysis CRS
    road_class: str = "local"
    width: float | None = None
    lanes: int = 2
    speed: float = 30.0                # km/h
    capacity: float | None = None      # veh/hour
    oneway: bool = False


@dataclass
class Facility:
    """§9.4 Facility."""

    id: str
    geometry: Any                      # point (analysis CRS)
    type: str = "generic"
    capacity: float | None = None
    service_radius: float | None = None  # m


@dataclass
class PopulationZone:
    """§9.5 Population zone."""

    id: str
    geometry: Any
    population: float = 0.0
    density: float | None = None
    demographics: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanningConstraint:
    """§9.6 Planning constraint."""

    id: str
    type: str
    geometry: Any
    severity: str = Severity.HARD.value
    weight: float = 1.0
    buffer: float = 0.0                # m, applied outward before testing
    source: str | None = None


@dataclass
class ScenarioChange:
    """§9.8 Scenario change (delta)."""

    scenario_id: str
    entity_type: str
    operation: str
    entity_id: str | None = None
    modified_attributes: dict[str, Any] = field(default_factory=dict)
    proposed_geometry: Any | None = None


@dataclass
class Scenario:
    """§9.7 Scenario header."""

    id: str
    base_dataset_version: int
    scenario_version: int = 0
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    status: str = "draft"


def records_of(items: Iterable[Any]) -> list[dict[str, Any]]:
    """Serialise dataclass records, dropping geometry objects."""
    out: list[dict[str, Any]] = []
    for it in items:
        d = {k: v for k, v in asdict(it).items() if k != "geometry"}
        out.append(d)
    return out
