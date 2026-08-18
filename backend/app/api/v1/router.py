"""v1 API aggregate router. ARCHITECTURE §5."""
from __future__ import annotations

from fastapi import APIRouter

<<<<<<< HEAD
from .routers import (agents, analysis, city, emergency, features, health,
                      layers, optimization, planning, results, scenario,
                      simulation)

api_router = APIRouter()
for m in (health, city, layers, features, planning, analysis,
          scenario, results, simulation, emergency, optimization, agents):
=======
from .routers import (agents, analysis, city, features, health, jobs, layers,
                      optimization, planning, results, scenario, simulation)

api_router = APIRouter()
for m in (health, city, layers, features, planning, analysis,
          scenario, results, simulation, optimization, agents, jobs):
>>>>>>> 57a663f36b368b058f1d6cbcbbc1de3a43e85b7d
    api_router.include_router(m.router)
