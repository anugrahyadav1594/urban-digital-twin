"""FastAPI dependencies. ARCHITECTURE §5."""
from __future__ import annotations

from typing import Annotated, Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from ..core.config import Settings, get_settings
from ..repositories import ResultsRepository, ScenarioRepository, SpatialRepository
from ..services import (AnalysisService, EmergencyService, PlanningService,
                        ScenarioService)
from ..storage.db import get_db


def db_session() -> Iterator[Session]:
    yield from get_db()


DbSession = Annotated[Session, Depends(db_session)]
Config = Annotated[Settings, Depends(get_settings)]

Spatial = Annotated[SpatialRepository, Depends(lambda s=Depends(db_session): SpatialRepository(s))]
Results = Annotated[ResultsRepository, Depends(lambda s=Depends(db_session): ResultsRepository(s))]
ScenarioRepo = Annotated[ScenarioRepository, Depends(lambda s=Depends(db_session): ScenarioRepository(s))]
Planning = Annotated[PlanningService, Depends(lambda s=Depends(db_session): PlanningService(s))]
Analysis = Annotated[AnalysisService, Depends(lambda s=Depends(db_session): AnalysisService(s))]
Scenarios = Annotated[ScenarioService, Depends(lambda s=Depends(db_session): ScenarioService(s))]
Emergency = Annotated[EmergencyService, Depends(lambda s=Depends(db_session): EmergencyService(s))]
