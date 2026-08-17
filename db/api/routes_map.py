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

@router.get("/master-map/{region_name}")
def get_master_map_by_region(region_name: str):
    """
    Fetches all spatial layers (roads, buildings, water, bridges) for a specified region
    and returns a unified EPSG:4326 GeoJSON FeatureCollection.
    Supported regions: adivali_devad, jnpt_port, chandigarh, rotterdam
    """
    from utils import REGIONAL_BOUNDS, STORAGE_CRS, ensure_crs
    from fastapi import HTTPException
    from sqlalchemy import text

    region_key = region_name.lower().strip()
    if region_key not in REGIONAL_BOUNDS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid region '{region_name}'. Valid regions are: {list(REGIONAL_BOUNDS.keys())}"
        )

    engine = get_engine()
    all_features = []
    layer_status = {}

    layers = ['roads', 'buildings', 'water', 'bridges']
    for layer in layers:
        try:
            table_name = f"{region_key}_{layer}"
            # Intelligent optimization for dense macro-cities
            where_clause = ""
            limit_clause = "LIMIT 3000"
            order_clause = ""

            if region_key == "rotterdam":
                if layer == "roads":
                    where_clause = "WHERE highway NOT IN ('footway', 'cycleway', 'steps', 'path', 'corridor', 'pedestrian')"
                    limit_clause = "LIMIT 1800"
                elif layer == "buildings":
                    order_clause = "ORDER BY ST_Area(geometry) DESC"
                    limit_clause = "LIMIT 1200"
            elif region_key == "chandigarh":
                if layer == "buildings":
                    limit_clause = "LIMIT 1500"

            sql = f"""
                SELECT *,
                       ST_AsGeoJSON(ST_Transform(ST_SetSRID(geometry, 4326), 4326)) AS geom_json
                FROM {table_name}
                {where_clause}
                {order_clause}
                {limit_clause};
            """
            with engine.connect() as conn:
                result = conn.execute(text(sql))
                rows = result.mappings().all()

            if not rows:
                layer_status[table_name] = "empty"
                continue

            features = []
            for row in rows:
                row_dict = dict(row)
                geom_json_str = row_dict.pop("geom_json", None)
                row_dict.pop("geometry", None)

                # Sanitize non-serializable values
                props = {}
                for k, v in row_dict.items():
                    if v is None:
                        props[k] = None
                    elif isinstance(v, (list, dict)):
                        props[k] = str(v)
                    else:
                        try:
                            json.dumps(v)
                            props[k] = v
                        except (TypeError, ValueError):
                            props[k] = str(v)

                props["layer"] = layer
                props["region"] = region_key

                if geom_json_str:
                    features.append({
                        "type": "Feature",
                        "properties": props,
                        "geometry": json.loads(geom_json_str)
                    })

            all_features.extend(features)
            layer_status[table_name] = f"{len(features)} features"

        except Exception as e:
            # Log error per table but continue stitching remaining layers
            layer_status[table_name] = f"error: {str(e)[:80]}"
            continue

    # Fallback to adivali_devad legacy map-data if batch tables not extracted yet
    if not all_features and region_key == "adivali_devad":
        return get_combined_map_data()

    combined = {
        "type": "FeatureCollection",
        "region": region_key,
        "feature_count": len(all_features),
        "layer_status": layer_status,
        "features": all_features
    }
    return Response(content=json.dumps(combined), media_type="application/json")


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
