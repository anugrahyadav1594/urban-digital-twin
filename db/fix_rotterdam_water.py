import requests
import geopandas as gpd
from shapely.geometry import Polygon, LineString
from db_config import get_engine
from utils import STORAGE_CRS

engine = get_engine()
S, W, N, E = 51.89, 4.45, 51.92, 4.50
ep = 'https://maps.mail.ru/osm/tools/overpass/api/interpreter'

# Water query
q_water = f"""[out:json][timeout:45];(way["water"]({S},{W},{N},{E});way["natural"="water"]({S},{W},{N},{E});way["waterway"]({S},{W},{N},{E}););out geom;"""
r = requests.post(ep, data={'data': q_water}, timeout=30)
data = r.json()
elems = data.get('elements', [])
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
                    'name': tags.get('name', 'Nieuwe Maas Waterway'),
                    'geometry': poly
                })
        except Exception:
            pass

if water_feats:
    gdf_w = gpd.GeoDataFrame(water_feats, geometry='geometry', crs=STORAGE_CRS)
    gdf_w.to_postgis('rotterdam_water', engine, if_exists='replace', index=False, dtype={'geometry': 'geometry'})
    print(f"✅ Saved {len(gdf_w)} water features to 'rotterdam_water'")

# Bridges query
q_bridges = f"""[out:json][timeout:45];(way["bridge"]({S},{W},{N},{E});way["bridge"="yes"]({S},{W},{N},{E}););out geom;"""
r_b = requests.post(ep, data={'data': q_bridges}, timeout=30)
data_b = r_b.json()
elems_b = data_b.get('elements', [])
bridge_feats = []
for el in elems_b:
    if 'geometry' in el and len(el['geometry']) >= 2:
        pts = [(pt['lon'], pt['lat']) for pt in el['geometry']]
        try:
            line = LineString(pts)
            if line.is_valid and not line.is_empty:
                tags = el.get('tags', {})
                bridge_feats.append({
                    'id': el.get('id'),
                    'name': tags.get('name', 'Erasmusbrug / Willemsbrug'),
                    'geometry': line
                })
        except Exception:
            pass

if bridge_feats:
    gdf_br = gpd.GeoDataFrame(bridge_feats, geometry='geometry', crs=STORAGE_CRS)
    gdf_br.to_postgis('rotterdam_bridges', engine, if_exists='replace', index=False, dtype={'geometry': 'geometry'})
    print(f"✅ Saved {len(gdf_br)} bridge features to 'rotterdam_bridges'")
