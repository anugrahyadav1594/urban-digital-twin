"""v1 API aggregate router. ARCHITECTURE §5."""
from __future__ import annotations

from fastapi import APIRouter

from .routers import (agents, analysis, city, emergency, features, health, jobs,
                      layers, optimization, planning, results, scenario,
                      simulation)

api_router = APIRouter()
for m in (health, city, layers, features, planning, analysis,
          scenario, results, simulation, emergency, optimization, agents, jobs):
    api_router.include_router(m.router)
