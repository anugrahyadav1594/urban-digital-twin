"""v1 API aggregate router. ARCHITECTURE §5."""
from __future__ import annotations

from fastapi import APIRouter

from .routers import (agents, analysis, city, emergency, features, health,
                      jobs, layers, optimization, planning, regions, results,
                      scenario, scoring, simulation)

api_router = APIRouter()
for m in (health, city, layers, regions, features, planning, analysis,
          scenario, scoring, results, simulation, emergency, optimization,
          agents, jobs):
    api_router.include_router(m.router)