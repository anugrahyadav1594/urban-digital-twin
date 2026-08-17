"""Engine/DB records -> frontend DTOs. ARCHITECTURE §5, §22.

The frontend (frontend/types/index.ts) expects camelCase objects with a fixed
shape: CityInfo, AnalysisResult{metrics,layers,entities}, FeatureRecord.
Engine output is snake_case EngineResult. This module is the single place that
translation happens, so routers stay thin and the contract is checkable.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

# Metric name -> (label, unit, better-direction) for the UI.
_METRIC_META: dict[str, tuple[str, str | None, str | None]] = {
    "coverage_ratio": ("Coverage", "ratio", "up"),
    "population_total": ("Population", "persons", None),
    "population_within_threshold": ("Population Covered", "persons", "up"),
    "population_unreachable": ("Unreachable", "persons", "down"),
    "mean_travel_time": ("Mean Travel Time", "s", "down"),
    "max_travel_time": ("Max Travel Time", "s", "down"),
    "facilities_evaluated": ("Facilities", "count", None),
    "parcels_evaluated": ("Parcels Evaluated", "count", None),
    "parcels_rejected": ("Parcels Rejected", "count", "down"),
    "nodes": ("Graph Nodes", "count", None),
    "edges": ("Graph Edges", "count", None),
    "connected_components": ("Components", "count", "down"),
    "largest_component_share": ("Largest Component", "ratio", "up"),
    "articulation_points": ("Critical Junctions", "count", "down"),
    "capacity_deficit": ("Capacity Deficit", "units", "down"),
    "required_capacity": ("Required Capacity", "units", None),
    "installed_capacity": ("Installed Capacity", "units", "up"),
    "projected_population": ("Projected Population", "persons", None),
    "zones_assigned": ("Zones Assigned", "count", "up"),
    "zones_unassigned": ("Zones Unassigned", "count", "down"),
}

_TYPE_MAP = {
    "site_suitability": "suitability",
    "accessibility": "accessibility",
    "emergency_response": "accessibility",
    "population_to_facility": "impact",
    "resilience": "risk",
    "demand_vs_capacity": "impact",
    "facility_location": "optimization",
    "max_coverage": "optimization",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _label(name: str) -> str:
    return _METRIC_META.get(name, (name.replace("_", " ").title(),))[0]


def metric_dto(m: dict[str, Any]) -> dict[str, Any]:
    name = m.get("name", "metric")
    meta = _METRIC_META.get(name)
    return {
        "key": name,
        "label": meta[0] if meta else name.replace("_", " ").title(),
        "value": m.get("value"),
        "unit": m.get("unit") or (meta[1] if meta else None),
        "better": meta[2] if meta else None,
    }


def entity_dto(rec: dict[str, Any]) -> dict[str, Any]:
    """A ranked record -> ResultEntity. Position is lon/lat for the globe."""
    eid = (rec.get("parcel_id") or rec.get("zone_id")
           or rec.get("facility_id") or rec.get("id") or "?")
    # MCDA criteria arrive as {name: {raw, normalized, weight, contribution,
    # direction, unit}}. The old numeric-only filter discarded all of them
    # (they are dicts) and fell through to internals like `raw_score`, so the
    # UI could not explain *why* a site ranked where it did. Surface the
    # weighted contribution per criterion, which is what the panel plots, and
    # keep the raw measurement alongside it.
    criteria = rec.get("criteria") or {}
    breakdown: dict[str, Any] = {}
    for name, detail in criteria.items():
        if isinstance(detail, dict):
            contrib = detail.get("contribution")
            raw = detail.get("raw")
            if isinstance(contrib, (int, float)):
                breakdown[name] = round(float(contrib), 6)
            if isinstance(raw, (int, float)):
                breakdown[f"{name}__raw"] = round(float(raw), 3)
        elif isinstance(detail, (int, float)):
            breakdown[name] = detail
    if not breakdown:
        # zone/facility records carry flat measurements instead of criteria
        source = rec.get("metrics") if isinstance(rec.get("metrics"), dict) else rec
        breakdown = {k: v for k, v in source.items()
                     if isinstance(v, (int, float))
                     and k not in ("rank", "raw_score", "penalty", "soft_penalty")}
    pos = rec.get("position_4326") or {}
    return {
        "entityId": str(eid),
        "score": float(rec.get("score") or rec.get("overall_score") or 0.0),
        "label": str(rec.get("label") or f"Parcel {eid}"),
        "position": {"lon": pos.get("lon", 0.0), "lat": pos.get("lat", 0.0)},
        "breakdown": breakdown,
    }


def coerce_scenario_id(value: Any) -> int | None:
    """Accept the frontend's scenario identifiers and return a DB id.

    The UI ships synthetic ids such as "scn_baseline" / "scn_plan_a" for its
    offline scenarios. Typing the field as int made those a 422, and because
    every client call falls back to mock data on error, real analyses were
    silently replaced by demo numbers. Baseline-ish ids mean "no scenario".
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value or None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return int(text) or None
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else None


def attach_positions(records: list[dict[str, Any]], session,
                     table: str = "land_parcels",
                     id_field: str = "parcel_id") -> None:
    """Fill position_4326 on ranked records, in place.

    Engine records carry ids and scores but no geometry, so the globe had
    nothing to plot and every entity landed at (0, 0) - the Gulf of Guinea.
    One query resolves all ids rather than one per record.
    """
    from sqlalchemy import text

    ids = []
    for r in records:
        raw = r.get(id_field)
        if raw is None:
            continue
        try:
            ids.append(int(str(raw).split("#")[0]))
        except ValueError:
            continue
    if not ids:
        return
    rows = session.execute(text(f"""
        SELECT id, ST_X(ST_Centroid(geometry)) AS lon,
                   ST_Y(ST_Centroid(geometry)) AS lat
        FROM {table} WHERE id = ANY(:ids)
    """), {"ids": list(set(ids))}).all()
    pos = {int(r[0]): {"lon": float(r[1]), "lat": float(r[2])} for r in rows}
    for r in records:
        raw = r.get(id_field)
        if raw is None:
            continue
        try:
            key = int(str(raw).split("#")[0])
        except ValueError:
            continue
        if key in pos:
            r["position_4326"] = pos[key]


def analysis_dto(result: dict[str, Any], title: str,
                 layers: Iterable[dict[str, Any]] = ()) -> dict[str, Any]:
    """EngineResult.to_dict() -> AnalysisResult the frontend can render."""
    prov = result.get("provenance") or {}
    rtype = _TYPE_MAP.get(result.get("result_type", ""), "impact")
    records = result.get("records") or []
    warnings = result.get("warnings") or []

    explanation = f"{title}."
    if prov.get("algorithm"):
        explanation += f" Algorithm {prov['algorithm']} v{prov.get('algorithm_version','?')}."
    explanation += f" Analysis CRS EPSG:{prov.get('analysis_srid','?')}."
    if warnings:
        explanation += " " + " ".join(str(w) for w in warnings[:2])

    return {
        "resultId": str(result.get("result_id") or ""),
        "type": rtype,
        "title": title,
        "datasetVersion": str(prov.get("dataset_version", "1")),
        "scenarioVersion": str(prov.get("scenario_version") or "base"),
        "createdAt": result.get("timestamp") or _now(),
        "metrics": [metric_dto(m) for m in (result.get("metrics") or [])],
        "layers": list(layers),
        "entities": [entity_dto(r) for r in records[:50]],
        "explanation": explanation,
        "warnings": warnings,
    }


def city_dto(counts: dict[str, int], extent: tuple | None,
             population: float, households: int, srid: int,
             dataset_version: int) -> dict[str, Any]:
    if extent:
        minx, miny, maxx, maxy = extent
        center = {"lon": (minx + maxx) / 2, "lat": (miny + maxy) / 2}
        # Rough planar km2 - adequate for a headline figure at city scale.
        area = abs((maxx - minx) * 111.0 * (maxy - miny) * 105.0)
    else:
        center, area = {"lon": 73.14, "lat": 18.997}, 0.0
    return {
        "id": "adivali-devad",
        "name": "Adivali-devad Sector",
        "state": "Maharashtra",
        "datasetVersion": str(dataset_version),
        "crs": f"EPSG:{srid}",
        "areaKm2": round(area, 2),
        "population": int(population),
        "households": int(households),
        "wards": counts.get("administrative_areas", 0),
        "updatedAt": _now(),
        "center": center,
        "counts": counts,
    }


def scenario_dto(row: dict[str, Any],
                 changes: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    status_map = {"draft": "draft", "frozen": "review",
                  "analyzed": "approved", "archived": "approved"}
    return {
        "id": str(row.get("id")),
        "name": row.get("name") or "Untitled",
        "status": status_map.get(str(row.get("status", "draft")).lower(), "draft"),
        "createdAt": str(row.get("created_at") or _now()),
        "horizon": int(row.get("horizon") or 2035),
        "populationGrowthPct": float(row.get("population_growth_pct") or 2.5),
        "changes": [
            {
                "id": str(c.get("id")),
                "type": _changtype(c.get("object_type")),
                "label": f"{c.get('operation','?')} {c.get('object_type','?')}",
                "detail": str(c.get("parameters") or {})[:200],
            }
            for c in (changes or [])
        ],
    }


def _change_type(object_type: Any) -> str:
    t = str(object_type or "").lower()
    if "facility" in t:
        return "facility"
    if "road" in t:
        return "road"
    if "population" in t or "zone" in t:
        return "population"
    return "zoning"
