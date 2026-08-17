"""v1 API aggregate router. ARCHITECTURE §5."""
from __future__ import annotations

from fastapi import APIRouter

from .routers import (agents, analysis, city, features, health, layers,
                      optimization, planning, results, scenario, simulation)

api_router = APIRouter()
for m in (health, city, layers, features, planning, analysis,
          scenario, results, simulation, optimization, agents):
    api_router.include_router(m.router)
