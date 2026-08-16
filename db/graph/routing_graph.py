import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import osmnx as ox
import networkx as nx
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, LineString
from etl.coordinate_utils import get_pilot_sector_polygon, STORAGE_CRS, PROJECTED_CRS, ensure_crs
from db_config import get_engine

def build_routing_graph_tables():
    """
    Builds the road network topology in PostGIS:
    - road_nodes (id, geometry)
    - road_edges (id, source_node, target_node, length_m, travel_time_sec, road_class, geometry)
    """
    print("🛣️ Building Road Network Topology & Routing Graph...")
    engine = get_engine()
    sector_polygon = get_pilot_sector_polygon()

    try:
        G = ox.graph_from_polygon(sector_polygon, network_type='drive')
        
        # 1. Road Nodes
        nodes_data = []
        for node_id, data in G.nodes(data=True):
            nodes_data.append({
                'id': node_id,
                'geometry': Point(data['x'], data['y'])
            })
        
        gdf_nodes = gpd.GeoDataFrame(nodes_data, geometry='geometry', crs=STORAGE_CRS)
        gdf_nodes = gdf_nodes.drop_duplicates(subset=['id']).copy()
        print(" -> Ingesting 'road_nodes' into PostGIS...")
        gdf_nodes.to_postgis('road_nodes', engine, if_exists='append', index=False)

        # 2. Road Edges
        edges_data = []
        for u, v, k, data in G.edges(keys=True, data=True):
            geom = data.get('geometry', LineString([Point(G.nodes[u]['x'], G.nodes[u]['y']), Point(G.nodes[v]['x'], G.nodes[v]['y'])]))
            length_m = float(data.get('length', 100.0))
            speed_kmh = float(data.get('maxspeed', 40.0) if not isinstance(data.get('maxspeed'), list) else 40.0)
            speed_mps = (speed_kmh * 1000.0) / 3600.0
            travel_time_sec = length_m / speed_mps if speed_mps > 0 else length_m / 11.1

            highway = data.get('highway', 'residential')
            road_class = highway[0] if isinstance(highway, list) else str(highway)

            edges_data.append({
                'source_node': u,
                'target_node': v,
                'length_m': round(length_m, 2),
                'travel_time_sec': round(travel_time_sec, 2),
                'road_class': road_class,
                'geometry': geom
            })

        gdf_edges = gpd.GeoDataFrame(edges_data, geometry='geometry', crs=STORAGE_CRS)
        print(" -> Ingesting 'road_edges' into PostGIS...")
        gdf_edges.to_postgis('road_edges', engine, if_exists='append', index=False)
        print("✅ Routing graph topology successfully built.")

    except Exception as e:
        print(f"⚠️ Error building routing graph: {e}")

def compute_shortest_path_networkx(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float):
    """
    Computes shortest path travel time (seconds) and distance (meters) between two points.
    """
    try:
        sector_poly = get_pilot_sector_polygon()
        G = ox.graph_from_polygon(sector_poly, network_type='drive')
        orig_node = ox.distance.nearest_nodes(G, origin_lon, origin_lat)
        dest_node = ox.distance.nearest_nodes(G, dest_lon, dest_lat)

        route_length = nx.shortest_path_length(G, orig_node, dest_node, weight='length')
        return {
            "origin_node": orig_node,
            "dest_node": dest_node,
            "distance_m": round(float(route_length), 2),
            "estimated_travel_time_min": round(float(route_length / 666.6), 2) # approx 40km/h
        }
    except Exception as e:
        # Fallback metric calculation
        p1 = Point(origin_lon, origin_lat)
        p2 = Point(dest_lon, dest_lat)
        dist_approx = p1.distance(p2) * 111000.0
        return {
            "distance_m": round(float(dist_approx), 2),
            "estimated_travel_time_min": round(float(dist_approx / 666.6), 2)
        }

if __name__ == "__main__":
    build_routing_graph_tables()
