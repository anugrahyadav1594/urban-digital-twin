"""Scenario resolution: Base City + Deltas = Proposed State. ARCHITECTURE §16.

The base collections are never mutated. Resolution copies records before
applying attribute patches, so the caller's base data is safe to reuse.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from ..contracts import EntityType, Operation

_COLLECTIONS = {
    EntityType.BUILDING.value: "buildings",
    EntityType.ROAD.value: "roads",
    EntityType.PARCEL.value: "parcels",
    EntityType.FACILITY.value: "facilities",
    EntityType.POPULATION_ZONE.value: "population_zones",
    EntityType.LANDUSE_ZONE.value: "landuse_zones",
    EntityType.INFRASTRUCTURE_ASSET.value: "infrastructure_assets",
    EntityType.CONSTRAINT.value: "constraints",
}


@dataclass
class ResolvedCity:
    """Materialised proposed state. Purely in-memory; nothing is persisted."""

    dataset_version: int
    scenario_id: str | None = None
    scenario_version: int | None = None
    buildings: list[Any] = field(default_factory=list)
    roads: list[Any] = field(default_factory=list)
    parcels: list[Any] = field(default_factory=list)
    facilities: list[Any] = field(default_factory=list)
    population_zones: list[Any] = field(default_factory=list)
    landuse_zones: list[Any] = field(default_factory=list)
    infrastructure_assets: list[Any] = field(default_factory=list)
    constraints: list[Any] = field(default_factory=list)
    applied: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)

    def counts(self) -> dict[str, int]:
        return {name: len(getattr(self, name)) for name in _COLLECTIONS.values()}


def _clone(rec: Any) -> Any:
    """Shallow copy the record, keeping the geometry object shared (immutable)."""
    return copy.copy(rec)


def resolve_scenario(
    base: Mapping[str, Sequence[Any]],
    changes: Sequence[Any] = (),
    dataset_version: int = 1,
    scenario_id: str | None = None,
    scenario_version: int | None = None,
    parameters: Mapping[str, Any] | None = None,
) -> ResolvedCity:
    """Apply scenario deltas onto base collections.

    base keys: buildings, roads, parcels, facilities, population_zones,
               landuse_zones, infrastructure_assets, constraints
    """
    city = ResolvedCity(
        dataset_version=dataset_version,
        scenario_id=scenario_id,
        scenario_version=scenario_version,
        parameters=dict(parameters or {}),
    )
    for attr in _COLLECTIONS.values():
        setattr(city, attr, [_clone(r) for r in base.get(attr, [])])

    index: dict[str, dict[str, Any]] = {}
    for et, attr in _COLLECTIONS.items():
        index[et] = {str(r.id): r for r in getattr(city, attr)}

    for ch in changes:
        et = ch.entity_type
        attr = _COLLECTIONS.get(et)
        if attr is None:
            city.rejected.append({
                "reason": "unknown entity_type", "entity_type": et,
                "entity_id": ch.entity_id,
            })
            continue

        coll: list[Any] = getattr(city, attr)
        op = ch.operation

        if op == Operation.DELETE.value:
            target = index[et].get(str(ch.entity_id))
            if target is None:
                city.rejected.append({
                    "reason": "delete target not found",
                    "entity_type": et, "entity_id": ch.entity_id,
                })
                continue
            coll.remove(target)
            index[et].pop(str(ch.entity_id), None)
            city.applied.append({"operation": op, "entity_type": et,
                                 "entity_id": ch.entity_id})

        elif op == Operation.MODIFY.value:
            target = index[et].get(str(ch.entity_id))
            if target is None:
                city.rejected.append({
                    "reason": "modify target not found",
                    "entity_type": et, "entity_id": ch.entity_id,
                })
                continue
            for k, v in (ch.modified_attributes or {}).items():
                if hasattr(target, k):
                    setattr(target, k, v)
                else:
                    target.__dict__.setdefault("attributes", {})[k] = v
            if ch.proposed_geometry is not None:
                target.geometry = ch.proposed_geometry
            city.applied.append({
                "operation": op, "entity_type": et, "entity_id": ch.entity_id,
                "attributes": list((ch.modified_attributes or {}).keys()),
            })

        elif op == Operation.ADD.value:
            new_id = str(ch.entity_id or f"proposed-{et}-{len(coll)+1}")
            if new_id in index[et]:
                city.rejected.append({
                    "reason": "add id already exists",
                    "entity_type": et, "entity_id": new_id,
                })
                continue
            rec = _build_record(et, new_id, ch)
            if rec is None:
                city.rejected.append({
                    "reason": "cannot construct record; geometry missing",
                    "entity_type": et, "entity_id": new_id,
                })
                continue
            coll.append(rec)
            index[et][new_id] = rec
            city.applied.append({"operation": op, "entity_type": et,
                                 "entity_id": new_id})
        else:
            city.rejected.append({
                "reason": f"unknown operation '{op}'",
                "entity_type": et, "entity_id": ch.entity_id,
            })

    return city


def _build_record(entity_type: str, new_id: str, ch: Any) -> Any | None:
    """Instantiate a new domain record from an ADD delta."""
    from ..contracts import (
        Building, Facility, Parcel, PlanningConstraint, PopulationZone, Road,
    )

    geom = ch.proposed_geometry
    if geom is None:
        return None
    attrs = dict(ch.modified_attributes or {})

    ctor = {
        EntityType.BUILDING.value: Building,
        EntityType.ROAD.value: Road,
        EntityType.PARCEL.value: Parcel,
        EntityType.FACILITY.value: Facility,
        EntityType.POPULATION_ZONE.value: PopulationZone,
        EntityType.CONSTRAINT.value: PlanningConstraint,
    }.get(entity_type)
    if ctor is None:
        return None

    valid = {f for f in ctor.__dataclass_fields__}  # type: ignore[attr-defined]
    kwargs = {k: v for k, v in attrs.items() if k in valid}
    kwargs["id"] = new_id
    kwargs["geometry"] = geom
    if entity_type == EntityType.CONSTRAINT.value and "type" not in kwargs:
        kwargs["type"] = attrs.get("type", "proposed")
    return ctor(**kwargs)
