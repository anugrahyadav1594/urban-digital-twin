from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes_map import router as map_router
from api.routes_gis_ops import router as gis_ops_router
from api.routes_mcda import router as mcda_router
from api.routes_scenarios import router as scenarios_router
from api.routes_3d_tiles import router as tiles_3d_router

app = FastAPI(
    title="NAGAR-X Spatial Database & GIS Engine API",
    description="AI-Powered Urban Planning & Infrastructure Digital Twin Backend (Adivali-devad / NAINA Sector)",
    version="1.0.0"
)

# Enable CORS for frontend integration (CesiumJS / Next.js / React)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Router Endpoints
app.include_router(map_router)
app.include_router(gis_ops_router)
app.include_router(mcda_router)
app.include_router(scenarios_router)
app.include_router(tiles_3d_router)

@app.get("/")
def root():
    return {
        "status": "online",
        "system": "NAGAR-X Urban Digital Twin Backend",
        "pilot_zone": "Adivali-devad / Chikhale Sector (NAINA Region, Navi Mumbai)",
        "crs": {"storage": "EPSG:4326", "projected": "EPSG:32643"},
        "docs_url": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
