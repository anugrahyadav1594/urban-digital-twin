"""Feature inspection. ARCHITECTURE §5 /features."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from ...deps import DbSession, Spatial

router = APIRouter(tags=["features"])

_KIND_TABLE = {"parcel": "land_parcels", "building": "buildings",
               "road": "roads", "facility": "facilities",
               "zone": "population_zones", "water": "water_bodies",
               "flood": "planning_constraints"}


@router.get("/features/nearby")
def nearby(repo: Spatial,
           lon: float = Query(..., ge=-180, le=180),
           lat: float = Query(..., ge=-90, le=90),
           radius_m: float = Query(2000, gt=0, le=50000)) -> dict[str, Any]:
    return {"facilities": repo.nearby_facilities(lon, lat, radius_m)}


@router.get("/features/{feature_id}")
def feature(feature_id: str, s: DbSession) -> dict[str, Any]:
    """Resolve 'kind:id' (e.g. 'facility:12') into a FeatureRecord."""
    # Map entity ids are "kind:id" but 3D layers append a per-ring index to
    # keep Cesium entity ids unique ("building:1297:1310"). Split on ALL
    # colons and keep the second field; a bare partition() left "1297:1310"
    # in raw and every polygon click 422'd.
    parts = feature_id.split(":")
    if len(parts) == 1:
        kind, raw = "facility", parts[0]
    else:
        kind, raw = parts[0], parts[1]
    table = _KIND_TABLE.get(kind)
    if table is None:
        raise HTTPException(404, f"unknown feature kind '{kind}'")
    try:
        fid = int(raw)
    except ValueError:
        raise HTTPException(422, "feature id must be numeric")

    row = s.execute(text(f"""
        SELECT to_jsonb(t) - 'geometry' AS attrs,
               ST_X(ST_Centroid(t.geometry)) AS lon,
               ST_Y(ST_Centroid(t.geometry)) AS lat
        FROM {table} t WHERE t.id = :id
    """), {"id": fid}).first()
    if row is None:
        raise HTTPException(404, f"{kind} {fid} not found")

    attrs = {k: v for k, v in row[0].items()
             if v is not None and not isinstance(v, (dict, list))}
    return {
        "id": f"{kind}:{fid}",
        "kind": kind,
        "name": str(attrs.get("name") or attrs.get("type") or f"{kind} {fid}"),
        "position": {"lon": row[1], "lat": row[2]},
        "attributes": attrs,
    }
