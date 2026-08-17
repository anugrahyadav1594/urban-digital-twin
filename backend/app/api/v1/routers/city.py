"""City inventory. ARCHITECTURE §5 /city."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ....core.config import get_settings
from ...dto import city_dto
from ...deps import Spatial

router = APIRouter(tags=["city"])


@router.get("/city")
def city(repo: Spatial) -> dict[str, Any]:
    cfg = get_settings()
    counts = repo.counts()
    pop = repo.total_population()
    return city_dto(counts, repo.city_extent(), pop,
                    households=int(pop / 4.5),
                    srid=cfg.storage_srid,
                    dataset_version=cfg.dataset_version)
