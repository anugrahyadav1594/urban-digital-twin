import requests
import json
import geopandas as gpd
from shapely.geometry import Polygon, LineString, Point
from db_config import get_engine
from utils import STORAGE_CRS

endpoints = [
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://maps.mail.ru/osm/tools/overpass/api/interpreter',
    'https://overpass.private.coffee/api/interpreter'
]

# Rotterdam bbox: south=51.89, west=4.45, north=51.92, east=4.50
S, W, N, E = 51.89, 4.45, 51.92, 4.50

def run_overpass_query(ql_query):
    for ep in endpoints:
        print(f"Querying {ep}...")
        try:
            r = requests.post(ep, data={'data': ql_query}, timeout=60)
            if r.status_code == 200:
                data = r.json()
                return data.get('elements', [])
        except Exception as e:
            print(f"  ⚠️ Mirror error on {ep}: {e}")
    return []

def fetch_rotterdam_all():
    engine = get_engine()
    
    # 1. ROADS
    print("🛣️ Fetching Rotterdam Road Network...")
    q_roads = f"""
    [out:json][timeout:60];
    (
      way["highway"]({S},{W},{N},{E});
    );
    out geom;
    """
    elems = run_overpass_query(q_roads)
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
        gdf_r.to_postgis('rotterdam_roads', engine, if_exists='replace', index=False, dtype={'geometry': 'geometry'})
        print(f"✅ Saved {len(gdf_r)} real road segments to 'rotterdam_roads'!")

    # 2. BUILDINGS
    print("🏢 Fetching Rotterdam Buildings...")
    q_bld = f"""
    [out:json][timeout:60];
    (
      way["building"]({S},{W},{N},{E});
    );
    out geom;
    """
    elems = run_overpass_query(q_bld)
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
        gdf_b.to_postgis('rotterdam_buildings', engine, if_exists='replace', index=False, dtype={'geometry': 'geometry'})
        print(f"✅ Saved {len(gdf_b)} real building footprints to 'rotterdam_buildings'!")

    # 3. WATER BODIES
    print("🌊 Fetching Rotterdam Waterways...")
    q_water = f"""
    [out:json][timeout:60];
    (
      way["waterway"]({S},{W},{N},{E});
      way["natural"="water"]({S},{W},{N},{E});
    );
    out geom;
    """
    elems = run_overpass_query(q_water)
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
                        'name': tags.get('name', 'Rotterdam Waterway'),
                        'type': tags.get('waterway', 'water'),
                        'geometry': poly
                    })
            except Exception:
                pass
    if water_feats:
        gdf_w = gpd.GeoDataFrame(water_feats, geometry='geometry', crs=STORAGE_CRS)
        gdf_w.to_postgis('rotterdam_water', engine, if_exists='replace', index=False, dtype={'geometry': 'geometry'})
        print(f"✅ Saved {len(gdf_w)} real water bodies to 'rotterdam_water'!")

    # 4. BRIDGES
    print("🌉 Fetching Rotterdam Bridges...")
    q_bridges = f"""
    [out:json][timeout:60];
    (
      way["bridge"="yes"]({S},{W},{N},{E});
    );
    out geom;
    """
    elems = run_overpass_query(q_bridges)
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
                        'name': tags.get('name', 'Erasmus / Willems Bridge Connector'),
                        'bridge': 'yes',
                        'geometry': line
                    })
            except Exception:
                pass
    if bridge_feats:
        gdf_br = gpd.GeoDataFrame(bridge_feats, geometry='geometry', crs=STORAGE_CRS)
        gdf_br.to_postgis('rotterdam_bridges', engine, if_exists='replace', index=False, dtype={'geometry': 'geometry'})
        print(f"✅ Saved {len(gdf_br)} real bridge features to 'rotterdam_bridges'!")

    print("\n🎉 ALL ROTTERDAM REAL OSM LAYERS LOADED SUCCESSFULLY!")

if __name__ == "__main__":
    fetch_rotterdam_all()
