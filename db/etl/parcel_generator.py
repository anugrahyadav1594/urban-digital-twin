import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Polygon, MultiPolygon, box
from shapely.ops import unary_union
from etl.coordinate_utils import get_pilot_sector_polygon, STORAGE_CRS, PROJECTED_CRS, ensure_crs
from etl.geometry_cleaner import clean_geometries
from db_config import get_engine

def generate_synthetic_land_parcels():
    """
    Generates realistic organic land parcels by partitioning the sector land 
    along actual road network boundaries (road-sliced blocks) rather than an artificial grid.
    """
    print("📐 Generating realistic road-sliced land parcels (Option B)...")
    engine = get_engine()
    sector_poly = get_pilot_sector_polygon()

    # 1. Fetch road geometries from PostGIS and buffer in projected metric CRS
    try:
        query_roads = "SELECT geometry FROM roads;"
        gdf_roads = gpd.read_postgis(query_roads, engine, geom_col='geometry')
        if not gdf_roads.empty:
            # Reproject to metric UTM Zone 43N for accurate 8m road buffer
            gdf_roads_proj = ensure_crs(gdf_roads, PROJECTED_CRS)
            road_buffers_proj = gdf_roads_proj['geometry'].buffer(8.0) # 8 meters
            road_union_proj = unary_union(road_buffers_proj)
            
            # Reproject back to STORAGE_CRS
            gdf_union = gpd.GeoDataFrame([{'geometry': road_union_proj}], crs=PROJECTED_CRS).to_crs(STORAGE_CRS)
            road_union = gdf_union['geometry'].iloc[0]
            
            # Slice sector polygon by road network
            sliced_land = sector_poly.difference(road_union)
        else:
            sliced_land = sector_poly
    except Exception:
        sliced_land = sector_poly

    # 2. Extract constituent polygon parcels
    polygon_list = []
    if isinstance(sliced_land, Polygon):
        polygon_list = [sliced_land]
    elif isinstance(sliced_land, MultiPolygon):
        polygon_list = list(sliced_land.geoms)

    parcels = []
    land_uses = ['residential', 'commercial', 'mixed_use', 'public_civic', 'green_space', 'industrial']
    zonings = ['R-1 Low Density', 'R-2 High Density', 'C-1 Commercial', 'Public Utility', 'Agricultural Zone']
    
    parcel_id = 1
    for poly in polygon_list:
        # Ignore tiny slivers (< ~300 sq meters in degrees)
        if poly.area > 0.0000005:
            centroid = poly.centroid
            cx, cy = centroid.x, centroid.y
            
            land_use = land_uses[parcel_id % len(land_uses)]
            zoning = zonings[parcel_id % len(zonings)]
            
            elevation_m = round(float(10.0 + (cx - 73.13) * 500.0 + np.sin(cy * 100) * 4.0), 2)
            slope_deg = round(float(0.5 + (parcel_id % 4) * 1.1), 2)
            flood_risk = round(float(0.02 + 0.12 * ((parcel_id) % 5 == 0)), 2)

            parcels.append({
                'land_use': land_use,
                'zoning': zoning,
                'development_status': 'candidate',
                'slope_deg': slope_deg,
                'elevation_m': elevation_m,
                'flood_risk': flood_risk,
                'geometry': poly,
                'source': 'Road-Sliced Sector Partition'
            })
            parcel_id += 1

    gdf_parcels = gpd.GeoDataFrame(parcels, geometry='geometry', crs=STORAGE_CRS)
    gdf_parcels = clean_geometries(gdf_parcels)

    print(f" -> Generated {len(gdf_parcels)} organic road-bounded land parcels.")
    print(" -> Writing 'land_parcels' table to PostGIS...")
    try:
        gdf_parcels.to_postgis('land_parcels', engine, if_exists='append', index=False)
        print("✅ Organic land parcels generated and loaded successfully.")
    except Exception as e:
        print(f"⚠️ Error writing land parcels to PostGIS: {e}")

if __name__ == "__main__":
    generate_synthetic_land_parcels()
