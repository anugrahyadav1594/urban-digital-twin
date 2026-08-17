"""Map layers and GeoJSON. ARCHITECTURE §5 /layers, §10."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ...deps import Spatial

router = APIRouter(tags=["layers"])

# Frontend LayerKind -> repository layer name (frontend/types/index.ts).
LAYER_ALIASES: dict[str, str] = {
    "buildings": "buildings",
    "parcels": "land_parcels",
    "landuse": "land_parcels",
    "roads": "roads",
    "highways": "roads",
    "population": "population_zones",
    "water": "water_bodies",
    "facilities": "facilities",
    "flood": "planning_constraints",
}

LAYER_META = [
    ("buildings", "Buildings", "Base", "#8ea9c1"),
    ("parcels", "Land Parcels", "Semantic", "#c9a227"),
    ("roads", "Road Network", "Base", "#5b6b7a"),
    ("population", "Population Zones", "Semantic", "#7fb069"),
    ("water", "Water Bodies", "Base", "#4a90d9"),
    ("facilities", "Civic Facilities", "Semantic", "#e07a5f"),
    ("flood", "Flood Constraints", "Risk", "#d1495b"),
]


@router.get("/layers")
def layers(repo: Spatial) -> list[dict[str, Any]]:
    counts = repo.counts()
    out = []
    for lid, name, group, color in LAYER_META:
        table = LAYER_ALIASES[lid]
        out.append({
            "id": lid, "name": name, "group": group,
            "visible": lid in ("buildings", "roads", "facilities"),
            "opacity": 1.0, "color": color,
            "count": counts.get(table, 0),
        })
    return out


@router.get("/layers/{layer_id}/geojson")
def layer_geojson(layer_id: str, repo: Spatial,
                  bbox: str | None = Query(None),
                  limit: int = Query(2000, ge=1, le=20000)) -> dict[str, Any]:
    table = LAYER_ALIASES.get(layer_id)
    if table is None:
        raise HTTPException(404, f"unknown layer '{layer_id}'")
    box = None
    if bbox:
        try:
            parts = [float(x) for x in bbox.split(",")]
            if len(parts) != 4:
                raise ValueError
            box = tuple(parts)
        except ValueError:
            raise HTTPException(422, "bbox must be minlon,minlat,maxlon,maxlat")
    try:
        return repo.features_geojson(table, bbox=box, limit=limit)
    except KeyError:
        raise HTTPException(404, f"unknown layer '{layer_id}'")
