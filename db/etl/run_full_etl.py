import os
import sys

# Ensure UTF-8 stdout encoding on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from db_config import get_engine, test_db_connection
from etl.fetch_osm import fetch_and_ingest_osm_data
from etl.parcel_generator import generate_synthetic_land_parcels
from etl.population_demographics import generate_demographics_and_wards
from graph.routing_graph import build_routing_graph_tables
from graph.knowledge_graph import build_city_knowledge_graph

def run_pipeline():
    print("=" * 60)
    print("[INFO] Starting NAGAR-X Full Master ETL Pipeline & Database Initialization")
    print("=" * 60)

    # 1. Verify PostGIS Connection
    db_ok = test_db_connection()
    if db_ok:
        engine = get_engine()
        # 2. Execute schema.sql & Truncate tables for a clean ETL run
        print("\n[STEP 1] Initializing PostGIS DDL Schema & Explicit GIST Indexes...")
        schema_path = os.path.join(os.path.dirname(__file__), '..', 'schema.sql')
        if os.path.exists(schema_path):
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            with engine.connect() as conn:
                conn.execute(text(schema_sql))
                # Truncate tables for a clean, idempotent pipeline run
                truncate_query = """
                TRUNCATE TABLE entity_relationships, spatial_entities, analysis_results, 
                               scenario_changes, scenarios, planning_constraints, water_bodies, 
                               land_parcels, population_zones, facilities, buildings, 
                               road_edges, road_nodes, roads, administrative_areas, dataset_metadata CASCADE;
                """
                conn.execute(text(truncate_query))
                conn.commit()
            print("[SUCCESS] Database Schema & GIST Indexes initialized and tables cleared for fresh ingestion.")
        else:
            print("[WARNING] schema.sql file not found.")

        # 3. OSM Data Ingestion
        print("\n[STEP 2] OpenStreetMap Layers Ingestion...")
        fetch_and_ingest_osm_data()

        # 4. Land Parcel Generation
        print("\n[STEP 3] Land Parcel Generation (Option B)...")
        generate_synthetic_land_parcels()

        # 5. Census Demographics
        print("\n[STEP 4] Census Demographics & Ward Allocation...")
        generate_demographics_and_wards()

        # 6. Routing Graph
        print("\n[STEP 5] Road Network Topology & Routing Graph...")
        build_routing_graph_tables()

        # 7. Knowledge Graph
        print("\n[STEP 6] City Knowledge Graph Ingestion...")
        build_city_knowledge_graph()

        print("\n" + "=" * 60)
        print("[SUCCESS] Full ETL Pipeline Executed Successfully!")
        print("=" * 60)
    else:
        print("\n[WARNING] Database is offline. The application will run in API mock/demo mode for development.")

if __name__ == "__main__":
    run_pipeline()
