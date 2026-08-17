"""Simulation. ARCHITECTURE §5 /simulation, §17."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ...dto import analysis_dto
from ...deps import Analysis, Spatial

router = APIRouter(prefix="/simulation", tags=["simulation"])


class PopulationRequest(BaseModel):
    base_year: int = 2025
    horizon_year: int = 2035
    annual_rate: float = 0.025
    facility_type: str = "hospital"


class FloodRequest(BaseModel):
    flood_level_m: float = 1.5
    return_period_years: int = 50


@router.post("/population")
def population(req: PopulationRequest, svc: Analysis) -> dict[str, Any]:
    out = svc.infrastructure_demand(
        req.facility_type, horizon_year=req.horizon_year,
        annual_rate=req.annual_rate, base_year=req.base_year)
    return analysis_dto(out, f"Population Projection {req.horizon_year}")


@router.post("/flood")
def flood(req: FloodRequest, repo: Spatial) -> dict[str, Any]:
    """Buildings exposed at a given flood depth, using stored water bodies.

    Honest scope: this is a proximity-based exposure screen, not a hydraulic
    model. §17 reserves real depth grids for a solver adapter.
    """
    from sqlalchemy import text
    buffer_m = max(req.flood_level_m, 0.1) * 120.0
    rows = repo.s.execute(text("""
        SELECT count(*) AS exposed,
               COALESCE(SUM(b.population_estimate), 0) AS people
        FROM buildings b
        WHERE EXISTS (
            SELECT 1 FROM water_bodies w
            WHERE ST_DWithin(b.geometry::geography, w.geometry::geography, :buf)
        )
    """), {"buf": buffer_m}).first()
    total = repo.counts().get("buildings", 0)
    exposed, people = (int(rows[0]), int(rows[1])) if rows else (0, 0)
    return {
        "resultId": "",
        "type": "risk",
        "title": f"Flood Exposure - {req.flood_level_m} m",
        "datasetVersion": "1",
        "scenarioVersion": "base",
        "createdAt": "",
        "metrics": [
            {"key": "buildings_exposed", "label": "Buildings Exposed",
             "value": exposed, "unit": "count", "better": "down"},
            {"key": "population_exposed", "label": "People Exposed",
             "value": people, "unit": "persons", "better": "down"},
            {"key": "exposure_share", "label": "Share of Building Stock",
             "value": round(exposed / total, 4) if total else 0.0,
             "unit": "ratio", "better": "down"},
        ],
        "layers": [{"id": "flood", "type": "polygons", "label": "Exposure Buffer"}],
        "entities": [],
        "explanation": (
            f"Proximity screen: buildings within {buffer_m:.0f} m of a mapped "
            f"water body at a {req.flood_level_m} m level, "
            f"{req.return_period_years}-year return period. Not a hydraulic model."
        ),
    }
