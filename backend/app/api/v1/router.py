from fastapi import APIRouter
from app.api.v1.routers import agents

api_router = APIRouter()
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
