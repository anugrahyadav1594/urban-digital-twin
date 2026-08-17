import requests
import json
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
from db_config import get_engine
from utils import STORAGE_CRS

endpoints = [
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://maps.mail.ru/osm/tools/overpass/api/interpreter',
    'https://overpass.private.coffee/api/interpreter'
]

def osm_to_polygons(elements):
    features = []
    for el in elements:
        geom_type = el.get('type')
        tags = el.get('tags', {})
        if geom_type == 'way' and 'geometry' in el:
            pts = [(pt['lon'], pt['lat']) for pt in el['geometry']]
            if len(pts) >= 3:
                try:
                    poly = Polygon(pts)
                    if poly.is_valid and not poly.is_empty:
                        features.append({
                            'id': el.get('id'),
                            'building_type': tags.get('building', 'yes'),
                            'name': tags.get('name', ''),
                            'geometry': poly
                        })
                except Exception:
                    pass
    return features

def fetch_chandigarh_buildings():
    # Chandigarh bounding box: south=30.73, west=76.765, north=30.75, east=76.79
    query = """
    [out:json][timeout:60];
    (
      way["building"](30.73,76.765,30.75,76.79);
      relation["building"](30.73,76.765,30.75,76.79);
    );
    out geom;
    """
    
    for ep in endpoints:
        print(f"Querying Overpass on {ep} for Chandigarh buildings...")
        try:
            r = requests.post(ep, data={'data': query}, timeout=45)
            if r.status_code == 200:
                data = r.json()
                elements = data.get('elements', [])
                print(f"✅ Received {len(elements)} OSM raw elements from {ep}!")
                
                features = osm_to_polygons(elements)
                print(f"✅ Converted to {len(features)} valid building polygon geometries!")
                
                if features:
                    gdf = gpd.GeoDataFrame(features, geometry='geometry', crs=STORAGE_CRS)
                    engine = get_engine()
                    gdf.to_postgis('chandigarh_buildings', engine, if_exists='replace', index=False, dtype={'geometry': 'geometry'})
                    print(f"🎉 Successfully saved {len(gdf)} real Chandigarh buildings to PostGIS table 'chandigarh_buildings'!")
                    return True
            else:
                print(f"⚠️ Status {r.status_code} from {ep}")
        except Exception as e:
            print(f"⚠️ Error on {ep}: {e}")
            
    print("❌ Failed on all mirrors.")
    return False

if __name__ == "__main__":
    fetch_chandigarh_buildings()
