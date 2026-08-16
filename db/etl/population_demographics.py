import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import geopandas as gpd
import pandas as pd
from shapely.geometry import box
from etl.coordinate_utils import get_pilot_sector_polygon, STORAGE_CRS
from etl.geometry_cleaner import clean_geometries, force_multi_polygon
from db_config import get_engine

def generate_demographics_and_wards():
    print("👥 Generating Census Wards and Population Zones...")
    engine = get_engine()
    sector_poly = get_pilot_sector_polygon()
    minx, miny, maxx, maxy = sector_poly.bounds
    midx = (minx + maxx) / 2
    midy = (miny + maxy) / 2

    # 1. Administrative Wards
    wards_data = [
        {"name": "Ward 1 - Adivali North", "type": "administrative_ward", "population": 24500, "geometry": box(minx, midy, midx, maxy).intersection(sector_poly)},
        {"name": "Ward 2 - Devad East", "type": "administrative_ward", "population": 31000, "geometry": box(midx, midy, maxx, maxy).intersection(sector_poly)},
        {"name": "Ward 3 - Chikhale Sector", "type": "administrative_ward", "population": 18200, "geometry": box(minx, miny, midx, midy).intersection(sector_poly)},
        {"name": "Ward 4 - NAINA Growth Zone", "type": "administrative_ward", "population": 29800, "geometry": box(midx, miny, maxx, midy).intersection(sector_poly)},
    ]

    gdf_wards = gpd.GeoDataFrame(wards_data, geometry='geometry', crs=STORAGE_CRS)
    gdf_wards = force_multi_polygon(clean_geometries(gdf_wards))
    gdf_wards['source'] = 'Census of India / NAINA Planning'

    print(" -> Ingesting 'administrative_areas' into PostGIS...")
    try:
        gdf_wards.to_postgis('administrative_areas', engine, if_exists='append', index=False)
    except Exception as e:
        print(f"⚠️ Error saving administrative areas: {e}")

    # 2. Population Density Zones (Grids)
    pop_zones = []
    for i, row in gdf_wards.iterrows():
        pop_zones.append({
            "population": row['population'],
            "households": int(row['population'] / 4.2),
            "density_per_sqkm": round(float(row['population'] / 1.5), 2),
            "geometry": row['geometry'].convex_hull,
            "source": "Census Grid Derivation"
        })

    gdf_pop = gpd.GeoDataFrame(pop_zones, geometry='geometry', crs=STORAGE_CRS)
    gdf_pop = clean_geometries(gdf_pop)

    print(" -> Ingesting 'population_zones' into PostGIS...")
    try:
        gdf_pop.to_postgis('population_zones', engine, if_exists='append', index=False)
        print("✅ Wards and demographic population zones loaded successfully.")
    except Exception as e:
        print(f"⚠️ Error saving population zones: {e}")

if __name__ == "__main__":
    generate_demographics_and_wards()
