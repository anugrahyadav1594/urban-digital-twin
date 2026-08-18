"""Persistence for engine results and scenarios. ARCHITECTURE §22, §16.

Results are immutable: re-running with changed parameters writes a NEW row.
The full provenance envelope (dataset_version, algorithm_version, parameters,
assumptions, units) is stored inside analysis_results.result_json so nothing
is lost against the existing NAGAR-X schema.
"""
from __future__ import annotations

import json
from typing import Any, Sequence

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from ..engines.contracts import EngineResult
from ..models import AnalysisResult, Scenario, ScenarioChange


class ResultsRepository:
    def __init__(self, session: Session):
        self.s = session

    def save(self, result: EngineResult, scenario_id: int | None = None) -> int:
        """Persist an EngineResult verbatim. Returns the new result id."""
        payload = json.loads(result.to_json())  # normalise Decimal/datetime
        row = AnalysisResult(
            scenario_id=scenario_id,
            analysis_type=result.result_type.upper(),
            result_json=payload,
        )
        self.s.add(row)
        self.s.flush()          # populate row.id without ending the transaction
        return int(row.id)

    def get(self, result_id: int) -> dict[str, Any] | None:
        row = self.s.get(AnalysisResult, result_id)
        if row is None:
            return None
        return {
            "id": row.id, "scenario_id": row.scenario_id,
            "analysis_type": row.analysis_type,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "result": row.result_json,
        }

    def list_for_scenario(
        self, scenario_id: int, analysis_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(AnalysisResult)
            .where(AnalysisResult.scenario_id == scenario_id)
            .order_by(desc(AnalysisResult.created_at))
            .limit(limit)
        )
        if analysis_type:
            stmt = stmt.where(AnalysisResult.analysis_type == analysis_type.upper())
        return [
            {"id": r.id, "analysis_type": r.analysis_type,
             "created_at": r.created_at.isoformat() if r.created_at else None,
             "result": r.result_json}
            for r in self.s.execute(stmt).scalars().all()
        ]

    def find_by_parameter_hash(self, param_hash: str) -> dict[str, Any] | None:
        """Idempotency lookup (§18.1): reuse an identical prior computation."""
        stmt = (
            select(AnalysisResult)
            .where(AnalysisResult.result_json["provenance"]["parameter_hash"]
                   .astext == param_hash)
            .order_by(desc(AnalysisResult.created_at))
            .limit(1)
        )
        row = self.s.execute(stmt).scalars().first()
        return None if row is None else {
            "id": row.id, "analysis_type": row.analysis_type,
            "result": row.result_json,
        }


class ScenarioRepository:
    """Scenario headers and deltas. The base city is never mutated (§16)."""

    def __init__(self, session: Session):
        self.s = session

    def create(self, name: str, description: str | None = None,
               base_version: str = "v1.0",
               created_by: str = "planner_admin",
               horizon: int = 2035,
               population_growth_pct: float = 2.5,
               status: str = "draft") -> int:
        row = Scenario(name=name, description=description,
                       base_version=base_version, created_by=created_by,
                       horizon=horizon, population_growth_pct=population_growth_pct,
                       status=status)
        self.s.add(row)
        self.s.flush()
        return int(row.id)

    def update(self, scenario_id: int, **kwargs) -> dict[str, Any] | None:
        row = self.s.get(Scenario, scenario_id)
        if row is None:
            return None
        for k, v in kwargs.items():
            if v is not None and hasattr(row, k):
                setattr(row, k, v)
        self.s.flush()
        return row.as_dict()

    def get(self, scenario_id: int) -> dict[str, Any] | None:
        row = self.s.get(Scenario, scenario_id)
        return None if row is None else row.as_dict()

    def list(self) -> list[dict[str, Any]]:
        return [r.as_dict() for r in self.s.execute(
            select(Scenario).order_by(Scenario.id)).scalars().all()]

    def add_change(self, scenario_id: int, object_type: str, operation: str,
                   parameters: dict[str, Any],
                   object_id: int | None = None) -> int:
        row = ScenarioChange(
            scenario_id=scenario_id, object_type=object_type,
            object_id=object_id, operation=operation.upper(),
            parameters=parameters,
        )
        self.s.add(row)
        self.s.flush()
        return int(row.id)

    def changes(self, scenario_id: int) -> list[dict[str, Any]]:
        rows = self.s.execute(
            select(ScenarioChange)
            .where(ScenarioChange.scenario_id == scenario_id)
            .order_by(ScenarioChange.id)
        ).scalars().all()
        return [r.as_dict() for r in rows]

    # NAGAR-X schema uses SQL-style verbs; the scenario engine (§16) uses
    # add/modify/delete. Translate rather than loosening the engine contract.
    _OPERATION_MAP = {
        "INSERT": "add", "ADD": "add", "CREATE": "add",
        "UPDATE": "modify", "MODIFY": "modify", "EDIT": "modify",
        "DELETE": "delete", "REMOVE": "delete", "DROP": "delete",
    }

    # Engine entity_type vocabulary (§16 _COLLECTIONS keys).
    _ENTITY_MAP = {
        "facility": "facility", "facilities": "facility",
        "parcel": "parcel", "land_parcel": "parcel", "land_parcels": "parcel",
        "road": "road", "roads": "road",
        "building": "building", "buildings": "building",
        "population_zone": "population_zone",
        "landuse_zone": "landuse_zone",
        "infrastructure_asset": "infrastructure_asset",
        "constraint": "constraint", "planning_constraint": "constraint",
    }

    def to_engine_changes(self, scenario_id: int) -> list[Any]:
        """Convert stored deltas into engine ScenarioChange records (§16).

        Translates the schema's INSERT/UPDATE/DELETE verbs and table-style
        object_type names into the engine vocabulary, and reprojects the
        GeoJSON geometry carried in the JSONB `parameters` payload.
        """
        from ..core.config import get_settings
        from ..engines.contracts import ScenarioChange as EngineChange
        from ..engines.crs import geojson_to_geometry, to_analysis

        srid = get_settings().analysis_srid
        out: list[Any] = []
        for r in self.changes(scenario_id):
            params = dict(r.get("parameters") or {})
            gj = params.pop("geometry", None)
            geom = None
            if gj:
                geom = to_analysis(geojson_to_geometry(gj), srid)
            raw_type = str(r["object_type"]).lower()
            raw_op = str(r["operation"]).upper()
            out.append(EngineChange(
                scenario_id=str(scenario_id),
                entity_type=self._ENTITY_MAP.get(raw_type, raw_type),
                operation=self._OPERATION_MAP.get(raw_op, raw_op.lower()),
                entity_id=None if r["object_id"] is None else str(r["object_id"]),
                modified_attributes=params,
                proposed_geometry=geom,
            ))
        return out
