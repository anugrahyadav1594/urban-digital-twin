"""v1 API aggregate router. ARCHITECTURE §5."""
from __future__ import annotations

from fastapi import APIRouter

<<<<<<< HEAD
from .routers import (agents, analysis, city, emergency, features, health,
                      jobs, layers, optimization, planning, results, scenario,
=======
from .routers import (agents, analysis, city, emergency, features, health, jobs,
                      layers, optimization, planning, results, scenario,
>>>>>>> 75f15e6ad521a3207cf21a1edd1816c5f5beb577
                      simulation)

api_router = APIRouter()
for m in (health, city, layers, features, planning, analysis,
          scenario, results, simulation, emergency, optimization, agents, jobs):
    api_router.include_router(m.router)
