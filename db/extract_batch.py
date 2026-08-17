import os
import sys
import requests
import json
import geopandas as gpd
from shapely.geometry import Polygon, LineString
from db_config import get_engine
from utils import REGIONAL_BOUNDS, STORAGE_CRS

# High-speed Overpass mirror pool
MIRRORS = [
    'https://maps.mail.ru/osm/tools/overpass/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://overpass.private.coffee/api/interpreter',
    'https://overpass-api.de/api/interpreter'
]

def query_overpass(ql_query):
    for ep in MIRRORS:
        try:
            r = requests.post(ep, data={'data': ql_query}, timeout=45)
            if r.status_code == 200:
                data = r.json()
                return data.get('elements', [])
        except Exception:
            continue
    return []

def extract_region(region_name, coords):
    print(f"\n🚀 Extracting Real OSM Layers for: [{region_name.upper()}]")
    engine = get_engine()
    
    # Calculate bounding box bounds (south, west, north, east)
    lons = [p[0] for p in coords]
    lats = [p[1] for p in coords]
    S, W, N, E = min(lats), min(lons), max(lats), max(lons)

    # 1. ROADS
    q_roads = f'[out:json][timeout:60];(way["highway"]({S},{W},{N},{E}););out geom;'
    elems = query_overpass(q_roads)
    road_feats = []
    for el in elems:
        if 'geometry' in el and len(el['geometry']) >= 2:
            pts = [(pt['lon'], pt['lat']) for pt in el['geometry']]
            try:
                line = LineString(pts)
                if line.is_valid and not line.is_empty:
                    tags = el.get('tags', {})
                    road_feats.append({
                        'id': el.get('id'),
                        'highway': tags.get('highway', 'road'),
                        'name': tags.get('name', ''),
                        'lanes': tags.get('lanes', 2),
                        'geometry': line
                    })
            except Exception:
                pass
    if road_feats:
        gdf_r = gpd.GeoDataFrame(road_feats, geometry='geometry', crs=STORAGE_CRS)
        gdf_r.to_postgis(f"{region_name}_roads", engine, if_exists='replace', index=False, dtype={'geometry': 'geometry'})
        print(f"  ✅ Roads: {len(gdf_r)} features → '{region_name}_roads'")

    # 2. BUILDINGS
    q_bld = f'[out:json][timeout:60];(way["building"]({S},{W},{N},{E});relation["building"]({S},{W},{N},{E}););out geom;'
    elems = query_overpass(q_bld)
    bld_feats = []
    for el in elems:
        if 'geometry' in el and len(el['geometry']) >= 3:
            pts = [(pt['lon'], pt['lat']) for pt in el['geometry']]
            try:
                poly = Polygon(pts)
                if poly.is_valid and not poly.is_empty:
                    tags = el.get('tags', {})
                    bld_feats.append({
                        'id': el.get('id'),
                        'building_type': tags.get('building', 'yes'),
                        'name': tags.get('name', ''),
                        'geometry': poly
                    })
            except Exception:
                pass
    if bld_feats:
        gdf_b = gpd.GeoDataFrame(bld_feats, geometry='geometry', crs=STORAGE_CRS)
        gdf_b.to_postgis(f"{region_name}_buildings", engine, if_exists='replace', index=False, dtype={'geometry': 'geometry'})
        print(f"  ✅ Buildings: {len(gdf_b)} features → '{region_name}_buildings'")

    # 3. WATER BODIES
    q_water = f'[out:json][timeout:60];(way["waterway"]({S},{W},{N},{E});way["natural"="water"]({S},{W},{N},{E}););out geom;'
    elems = query_overpass(q_water)
    water_feats = []
    for el in elems:
        if 'geometry' in el and len(el['geometry']) >= 3:
            pts = [(pt['lon'], pt['lat']) for pt in el['geometry']]
            try:
                poly = Polygon(pts)
                if poly.is_valid and not poly.is_empty:
                    tags = el.get('tags', {})
                    water_feats.append({
                        'id': el.get('id'),
                        'name': tags.get('name', 'Water Body'),
                        'type': tags.get('waterway', 'water'),
                        'geometry': poly
                    })
            except Exception:
                pass
    if water_feats:
        gdf_w = gpd.GeoDataFrame(water_feats, geometry='geometry', crs=STORAGE_CRS)
        gdf_w.to_postgis(f"{region_name}_water", engine, if_exists='replace', index=False, dtype={'geometry': 'geometry'})
        print(f"  ✅ Water: {len(gdf_w)} features → '{region_name}_water'")

    # 4. BRIDGES
    q_bridges = f'[out:json][timeout:60];(way["bridge"="yes"]({S},{W},{N},{E});way["bridge"]({S},{W},{N},{E}););out geom;'
    elems = query_overpass(q_bridges)
    bridge_feats = []
    for el in elems:
        if 'geometry' in el and len(el['geometry']) >= 2:
            pts = [(pt['lon'], pt['lat']) for pt in el['geometry']]
            try:
                line = LineString(pts)
                if line.is_valid and not line.is_empty:
                    tags = el.get('tags', {})
                    bridge_feats.append({
                        'id': el.get('id'),
                        'name': tags.get('name', 'Connector Bridge'),
                        'bridge': 'yes',
                        'geometry': line
                    })
            except Exception:
                pass
    if bridge_feats:
        gdf_br = gpd.GeoDataFrame(bridge_feats, geometry='geometry', crs=STORAGE_CRS)
        gdf_br.to_postgis(f"{region_name}_bridges", engine, if_exists='replace', index=False, dtype={'geometry': 'geometry'})
        print(f"  ✅ Bridges: {len(gdf_br)} features → '{region_name}_bridges'")

def run_batch_extraction():
    print("=" * 75)
    print("🌐 RUNNING HIGH-SPEED OSM BATCH EXTRACTION FOR ALL 4 REGIONS")
    print("=" * 75)
    for region_name, coords in REGIONAL_BOUNDS.items():
        extract_region(region_name, coords)
    print("\n" + "=" * 75)
    print("🎉 ALL 4 REGIONS EXTRACTED WITH REAL OSM DATA!")
    print("=" * 75)

if __name__ == "__main__":
    run_batch_extraction()
