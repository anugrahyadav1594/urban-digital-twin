from fastapi import APIRouter, Response
import geopandas as gpd
import pandas as pd
import json
from db_config import get_engine
from etl.coordinate_utils import get_pilot_sector_polygon, STORAGE_CRS, ensure_crs
from etl.parcel_generator import generate_synthetic_land_parcels

router = APIRouter(prefix="/api", tags=["2D Map Layers & Metadata"])

def get_demo_combined_geojson():
    """Generates standalone GeoJSON for demo/testing when database is offline."""
    sector_poly = get_pilot_sector_polygon()
    minx, miny, maxx, maxy = sector_poly.bounds

    features = []
    # Add candidate parcel demo feature
    features.append({
        "type": "Feature",
        "properties": {"id": 14, "layer": "land_parcels", "land_use": "mixed_use", "flood_risk": 0.05},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[73.132, 18.992], [73.138, 18.992], [73.138, 18.998], [73.132, 18.998], [73.132, 18.992]]]
        }
    })
    # Add hospital demo feature
    features.append({
        "type": "Feature",
        "properties": {"id": 1, "layer": "facilities", "type": "hospital", "name": "Adivali General Hospital"},
        "geometry": {
            "type": "Point",
            "coordinates": [73.135, 18.995]
        }
    })
    return {"type": "FeatureCollection", "features": features}

@router.get("/map-data")
def get_combined_map_data(include_parcels: bool = False):
    """
    Fetches combined spatial layers (roads, buildings, facilities, administrative areas) as unified GeoJSON.
    Pass include_parcels=true if land parcel polygons are specifically needed.
    """
    try:
        engine = get_engine()
        all_features = []
        
        tables = ['roads', 'buildings', 'facilities', 'administrative_areas']
        if include_parcels:
            tables.append('land_parcels')

        for tbl in tables:
            try:
                gdf = gpd.read_postgis(f"SELECT * FROM {tbl};", engine, geom_col='geometry')
                if not gdf.empty:
                    gdf = ensure_crs(gdf, STORAGE_CRS)
                    for col in gdf.columns:
                        if col != 'geometry' and pd.api.types.is_datetime64_any_dtype(gdf[col]):
                            gdf[col] = gdf[col].astype(str)
                    geojson_dict = json.loads(gdf.to_json())
                    for feat in geojson_dict["features"]:
                        feat["properties"]["layer"] = tbl
                        all_features.append(feat)
            except Exception:
                continue

        if not all_features:
            return get_demo_combined_geojson()

        combined = {"type": "FeatureCollection", "features": all_features}
        return Response(content=json.dumps(combined), media_type="application/json")
    except Exception:
        return get_demo_combined_geojson()

@router.get("/layers/{layer_name}")
def get_layer(layer_name: str):
    """Fetches a specific spatial layer as GeoJSON."""
    try:
        engine = get_engine()
        gdf = gpd.read_postgis(f"SELECT * FROM {layer_name};", engine, geom_col='geometry')
        gdf = ensure_crs(gdf, STORAGE_CRS)
        return Response(content=gdf.to_json(), media_type="application/json")
    except Exception as e:
        return {"error": f"Layer '{layer_name}' not found or database offline.", "details": str(e)}

@router.get("/metadata")
def get_metadata():
    """Returns dataset provenance and metadata records for auditability."""
    try:
        engine = get_engine()
        df = pd.read_sql("SELECT * FROM dataset_metadata;", engine)
        return df.to_dict(orient="records")
    except Exception:
        return [
            {"dataset_name": "OpenStreetMap Base Layers", "source": "OpenStreetMap Foundation", "license": "ODbL", "crs": "EPSG:4326"},
            {"dataset_name": "Google Open Buildings V3", "source": "Google Earth Engine", "license": "CC BY 4.0", "crs": "EPSG:4326"},
            {"dataset_name": "Copernicus DEM", "source": "ESA / Copernicus", "license": "Open Access", "crs": "EPSG:4326"}
        ]
