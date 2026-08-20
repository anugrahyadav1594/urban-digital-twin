"""City scoring, development packages and guided scenarios.

Product report §1 (packages), §2 (scoring), §3 (guided scenario builder).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ...deps import DbSession
from ....engines.scoring.benchmarks import BENCHMARKS, PAIRING
from ....engines.scoring.dimensions import DIMENSIONS
from ....services.scoring_service import ScoringService

router = APIRouter(tags=["scoring"])


class WeightsRequest(BaseModel):
    """Per-dimension weight overrides. Report §2 keeps these configurable."""
    weights: dict[str, float] | None = None


class PackageRequest(WeightsRequest):
    region: str = "adivali_devad"
    targetUplift: float = Field(10.0, ge=0.5, le=60.0)
    priorities: list[str] = Field(default_factory=list)
    budget: float | None = Field(None, gt=0)
    maxActions: int = Field(12, ge=1, le=40)


class Variant(BaseModel):
    name: str = "Scenario"
    targetUplift: float = Field(10.0, ge=0.5, le=60.0)
    priorities: list[str] = Field(default_factory=list)
    budget: float | None = Field(None, gt=0)
    maxActions: int = Field(12, ge=1, le=40)


class CompareRequest(WeightsRequest):
    region: str = "adivali_devad"
    variants: list[Variant] = Field(default_factory=list)


@router.get("/scoring/dimensions")
def list_dimensions() -> dict[str, Any]:
    """The scoring framework itself, so the UI can render it generically."""
    return {
        "profileVersion": "city-score-1.0.0",
        "dimensions": [
            {
                "key": d.key, "label": d.label, "unit": d.unit,
                "floor": d.floor, "target": d.target,
                "direction": d.direction, "defaultWeight": d.weight,
                "description": d.description, "requires": list(d.requires),
            }
            for d in DIMENSIONS
        ],
        "benchmarks": [
            {"key": b.key, "label": b.label, "rationale": b.rationale}
            for b in BENCHMARKS.values()
        ],
        "pairing": PAIRING,
    }


@router.get("/scoring/city")
def score_city_endpoint(
    s: DbSession,
    region: str = Query("adivali_devad"),
    persist: bool = Query(False),
) -> dict[str, Any]:
    """City scorecard: overall score, every dimension, benchmark gap."""
    try:
        return ScoringService(s).score(region=region, persist=persist)
    except Exception as exc:                                 # noqa: BLE001
        raise HTTPException(500, f"{type(exc).__name__}: {exc}") from exc


@router.post("/scoring/city")
def score_city_weighted(s: DbSession, body: PackageRequest) -> dict[str, Any]:
    """Same scorecard with caller-supplied dimension weights."""
    try:
        return ScoringService(s).score(region=body.region,
                                       weights=body.weights)
    except Exception as exc:                                 # noqa: BLE001
        raise HTTPException(500, f"{type(exc).__name__}: {exc}") from exc


@router.post("/scoring/package")
def development_package(s: DbSession, body: PackageRequest) -> dict[str, Any]:
    """Generate a coordinated development package from the score gaps."""
    try:
        return ScoringService(s).package(
            region=body.region,
            target_uplift=body.targetUplift,
            priorities=tuple(body.priorities),
            budget=body.budget,
            weights=body.weights,
            max_actions=body.maxActions,
        )
    except Exception as exc:                                 # noqa: BLE001
        raise HTTPException(500, f"{type(exc).__name__}: {exc}") from exc


@router.post("/scoring/compare")
def compare_packages(s: DbSession, body: CompareRequest) -> dict[str, Any]:
    """Build Scenario A/B/C and compare them on common KPIs."""
    try:
        return ScoringService(s).compare_packages(
            region=body.region,
            variants=[v.model_dump() for v in body.variants],
            weights=body.weights,
        )
    except Exception as exc:                                 # noqa: BLE001
        raise HTTPException(500, f"{type(exc).__name__}: {exc}") from exc