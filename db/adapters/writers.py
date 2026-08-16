"""Engine results -> PostGIS persistence.

ARCHITECTURE §22. Every result is persisted before it is returned, with full
provenance, so any recommendation is reproducible and auditable.

Results land in analysis_results(scenario_id, analysis_type, result_json).
"""
from __future__ import annotations

import json
from typing import Any, Sequence

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.engines.contracts import EngineResult

from .geometry import ANALYSIS_SRID, to_storage


def _json_default(obj: Any) -> Any:
    from decimal import Decimal
    if isinstance(obj, Decimal):
        return float(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "__geo_interface__"):
        return obj.__geo_interface__
    return str(obj)


def save_result(
    engine: Engine,
    result: EngineResult,
    scenario_id: int | None = None,
    analysis_type: str | None = None,
) -> int | None:
    """Persist an EngineResult. Returns the analysis_results row id.

    The stored payload is result.to_dict(), which already contains the
    reproducibility tuple: dataset_version, scenario_version,
    algorithm_version and parameters (§25).
    """
    payload = result.to_dict()
    atype = (analysis_type or result.result_type).upper()

    sql = text(
        "INSERT INTO analysis_results (scenario_id, analysis_type, result_json) "
        "VALUES (:sid, :atype, CAST(:payload AS JSONB)) RETURNING id"
    )
    try:
        with engine.begin() as conn:
            row = conn.execute(sql, {
                "sid": scenario_id,
                "atype": atype,
                "payload": json.dumps(payload, default=_json_default),
            }).fetchone()
            return int(row[0]) if row else None
    except Exception as exc:                      # pragma: no cover
        print(f"[WARNING] could not persist result '{atype}': {exc}")
        return None


def load_result(engine: Engine, result_id: int) -> dict[str, Any] | None:
    sql = text(
        "SELECT id, scenario_id, analysis_type, result_json, created_at "
        "FROM analysis_results WHERE id = :rid"
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"rid": result_id}).mappings().fetchone()
        if row is None:
            return None
        payload = row["result_json"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return {
            "id": row["id"],
            "scenario_id": row["scenario_id"],
            "analysis_type": row["analysis_type"],
            "created_at": str(row["created_at"]),
            "result": payload,
        }


def list_results(
    engine: Engine,
    scenario_id: int | None = None,
    analysis_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    clauses, params = [], {"lim": limit}
    if scenario_id is not None:
        clauses.append("scenario_id = :sid")
        params["sid"] = scenario_id
    if analysis_type:
        clauses.append("analysis_type = :atype")
        params["atype"] = analysis_type.upper()
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    sql = text(
        "SELECT id, scenario_id, analysis_type, created_at FROM analysis_results"
        + where + " ORDER BY created_at DESC LIMIT :lim"
    )
    with engine.connect() as conn:
        return [dict(r) | {"created_at": str(r["created_at"])}
                for r in conn.execute(sql, params).mappings()]


def result_to_geojson(
    result: EngineResult,
    geometries: dict[str, Any],
    analysis_srid: int = ANALYSIS_SRID,
) -> dict[str, Any]:
    """Convert a result's records into EPSG:4326 GeoJSON for CesiumJS (§23).

    geometries maps a record identifier to its analysis-CRS shapely geometry;
    everything is reprojected back to 4326 for the browser.
    """
    features = []
    for rec in result.records:
        key = str(
            rec.get("parcel_id") or rec.get("candidate_id")
            or rec.get("zone_id") or rec.get("facility_id") or ""
        )
        geom = geometries.get(key)
        if geom is None:
            continue
        props = {k: v for k, v in rec.items() if k != "criteria"}
        props["result_type"] = result.result_type
        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": to_storage(geom, analysis_srid).__geo_interface__,
        })
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "result_type": result.result_type,
            "provenance": result.provenance.to_dict(),
            "metrics": [m.to_dict() for m in result.metrics],
            "warnings": result.warnings,
        },
    }
