"""Regional master-map layers. ARCHITECTURE §5 /regions, §10.

The pilot sector (Adivali-devad) is served by /layers from the canonical
`roads` / `buildings` / ... tables. The batch extractor (db/extract_batch.py)
additionally writes per-region tables named ``{region}_{layer}`` for three
comparison areas. Those had no route on the main API, so only the pilot was
ever reachable from the UI.

This exposes them through the same server rather than requiring the separate
db/api app to be running as well.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from ...deps import DbSession

router = APIRouter(tags=["regions"])

# Keep in step with db/utils.py REGIONAL_BOUNDS.
REGIONS: dict[str, dict[str, Any]] = {
    "adivali_devad": {
        "label": "Adivali-devad (NAINA)",
        "note": "Pilot sector. TPS-4 boundary near Panvel.",
        "bounds": (73.1300, 18.9900, 73.1500, 19.0050),
        # The pilot lives in the canonical tables, not "adivali_devad_*".
        "tables": {"roads": "roads", "buildings": "buildings",
                   "water": "water_bodies"},
    },
    "jnpt_port": {
        "label": "JNPT Port",
        "note": "Logistics zone; heavy maritime infrastructure.",
        "bounds": (72.9300, 18.9300, 73.0000, 18.9800),
        "tables": None,
    },
    "chandigarh": {
        "label": "Chandigarh Sector 17",
        "note": "Master-planned grid, for morphology comparison.",
        "bounds": (76.7650, 30.7300, 76.7900, 30.7500),
        "tables": None,
    },
    "rotterdam": {
        "label": "Rotterdam",
        "note": "Global benchmark port city.",
        "bounds": (4.4500, 51.8900, 4.5000, 51.9200),
        "tables": None,
    },
}

LAYERS = ("roads", "buildings", "water", "bridges")

# Per-region render caps. Dense cities would otherwise return tens of
# thousands of features and stall the globe.
LIMITS: dict[str, dict[str, int]] = {
    "rotterdam": {"roads": 1800, "buildings": 1200},
    "chandigarh": {"buildings": 1500},
}
DEFAULT_LIMIT = 3000

# Paths and pedestrian ways add no structure at city-comparison zoom.
ROAD_EXCLUDE = ("footway", "cycleway", "steps", "path", "corridor", "pedestrian")


def _table_for(region: str, layer: str) -> str:
    override = (REGIONS[region].get("tables") or {}).get(layer)
    return override or f"{region}_{layer}"


def _table_exists(s: Any, table: str) -> bool:
    return bool(s.execute(text("SELECT to_regclass(:t)"),
                          {"t": f"public.{table}"}).scalar())


def _geom_column(s: Any, table: str) -> str | None:
    """Geometry column name, or None. Extractors are not consistent."""
    row = s.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = :t
          AND udt_name IN ('geometry', 'geography')
        ORDER BY column_name LIMIT 1
    """), {"t": table}).first()
    return row[0] if row else None


@router.get("/regions")
def list_regions(s: DbSession) -> list[dict[str, Any]]:
    """Every region, with which layers actually have data.

    `available` drives the UI: a region with no extracted tables is listed but
    shown as unavailable, rather than silently missing.
    """
    out: list[dict[str, Any]] = []
    for rid, spec in REGIONS.items():
        layers: dict[str, int] = {}
        for layer in LAYERS:
            table = _table_for(rid, layer)
            try:
                if not _table_exists(s, table):
                    continue
                n = s.execute(text(f"SELECT count(*) FROM {table}")).scalar()
            except Exception:                                # noqa: BLE001
                continue
            if n:
                layers[layer] = int(n)
        minx, miny, maxx, maxy = spec["bounds"]
        out.append({
            "id": rid,
            "label": spec["label"],
            "note": spec["note"],
            "bounds": [minx, miny, maxx, maxy],
            "center": {"lon": (minx + maxx) / 2, "lat": (miny + maxy) / 2},
            "layers": layers,
            "featureCount": sum(layers.values()),
            "available": bool(layers),
        })
    return out


@router.get("/regions/{region_id}/geojson")
def region_geojson(region_id: str, s: DbSession,
                   layer: str | None = Query(None),
                   limit: int | None = Query(None, ge=1, le=20000)
                   ) -> dict[str, Any]:
    """All layers of one region as a single FeatureCollection.

    Each feature carries `layer` and `region` in its properties so the client
    can style and toggle without a request per layer.
    """
    rid = region_id.lower().strip()
    if rid not in REGIONS:
        raise HTTPException(
            404, f"unknown region '{region_id}'; valid: {sorted(REGIONS)}")

    wanted = [layer] if layer else list(LAYERS)
    bad = [x for x in wanted if x not in LAYERS]
    if bad:
        raise HTTPException(422, f"unknown layer(s): {bad}; valid: {list(LAYERS)}")

    features: list[dict[str, Any]] = []
    status: dict[str, str] = {}

    for lyr in wanted:
        table = _table_for(rid, lyr)
        try:
            if not _table_exists(s, table):
                status[lyr] = "no table"
                continue
            gcol = _geom_column(s, table)
            if gcol is None:
                status[lyr] = "no geometry column"
                continue

            cap = limit or LIMITS.get(rid, {}).get(lyr, DEFAULT_LIMIT)
            where, order = "", ""
            params: dict[str, Any] = {"lim": int(cap)}

            # Trim noise in the dense benchmark city only.
            if rid == "rotterdam" and lyr == "roads":
                cols = {r[0] for r in s.execute(text("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema='public' AND table_name=:t
                """), {"t": table})}
                if "highway" in cols:
                    where = "WHERE highway IS NULL OR highway <> ALL(:excl)"
                    params["excl"] = list(ROAD_EXCLUDE)
            if rid in ("rotterdam", "chandigarh") and lyr == "buildings":
                order = f"ORDER BY ST_Area({gcol}::geography) DESC"

            rows = s.execute(text(f"""
                SELECT ST_AsGeoJSON(ST_Transform(ST_SetSRID({gcol}, 4326), 4326)) AS g
                FROM {table} {where} {order} LIMIT :lim
            """), params).all()

            n = 0
            for (g,) in rows:
                if not g:
                    continue
                features.append({
                    "type": "Feature",
                    "properties": {"layer": lyr, "region": rid},
                    "geometry": json.loads(g),
                })
                n += 1
            status[lyr] = f"{n} features"
        except Exception as exc:                             # noqa: BLE001
            # One bad table must not lose the rest of the region.
            status[lyr] = f"error: {type(exc).__name__}"
            continue

    minx, miny, maxx, maxy = REGIONS[rid]["bounds"]
    return {
        "type": "FeatureCollection",
        "region": rid,
        "label": REGIONS[rid]["label"],
        "bounds": [minx, miny, maxx, maxy],
        "center": {"lon": (minx + maxx) / 2, "lat": (miny + maxy) / 2},
        "layerStatus": status,
        "featureCount": len(features),
        "features": features,
    }