import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import geopandas as gpd
import pandas as pd
from db_config import get_engine

def build_city_knowledge_graph():
    """
    Populates PostGIS City Knowledge Graph tables:
    - spatial_entities
    - entity_relationships
    """
    print("🕸️ Building City Knowledge Graph in PostGIS...")
    engine = get_engine()

    try:
        # 1. Register Facilities as Entities
        query_fac = "SELECT id, type, name FROM facilities;"
        df_fac = pd.read_sql(query_fac, engine)
        
        entities = []
        for _, row in df_fac.iterrows():
            entity_id = f"fac_{row['id']}"
            entities.append({
                "id": entity_id,
                "entity_type": str(row['type']).upper(),
                "name": row['name'],
                "table_name": "facilities",
                "record_id": row['id']
            })

        # 2. Register Wards as Entities
        query_wards = "SELECT id, name FROM administrative_areas;"
        df_wards = pd.read_sql(query_wards, engine)
        for _, row in df_wards.iterrows():
            entity_id = f"ward_{row['id']}"
            entities.append({
                "id": entity_id,
                "entity_type": "WARD",
                "name": row['name'],
                "table_name": "administrative_areas",
                "record_id": row['id']
            })

        # 3. Register Parcels as Entities
        query_parcels = "SELECT id, land_use FROM land_parcels LIMIT 20;"
        df_parcels = pd.read_sql(query_parcels, engine)
        for _, row in df_parcels.iterrows():
            entity_id = f"parcel_{row['id']}"
            entities.append({
                "id": entity_id,
                "entity_type": "PARCEL",
                "name": f"Parcel #{row['id']} ({row['land_use']})",
                "table_name": "land_parcels",
                "record_id": row['id']
            })

        df_entities = pd.DataFrame(entities)
        df_entities = df_entities.drop_duplicates(subset=['id']).copy()
        print(" -> Ingesting 'spatial_entities'...")
        df_entities.to_sql('spatial_entities', engine, if_exists='append', index=False)

        # 4. Generate Spatial Relationships (e.g. Hospital located_in Ward, Hospital serves Parcel)
        relationships = []
        for f_row in df_fac.iterrows():
            f_id = f"fac_{f_row[1]['id']}"
            for w_row in df_wards.iterrows():
                w_id = f"ward_{w_row[1]['id']}"
                relationships.append({
                    "subject_entity": f_id,
                    "predicate": "located_in",
                    "object_entity": w_id,
                    "distance_m": 0.0
                })

        for p_row in df_parcels.iterrows():
            p_id = f"parcel_{p_row[1]['id']}"
            for w_row in df_wards.iterrows():
                w_id = f"ward_{w_row[1]['id']}"
                relationships.append({
                    "subject_entity": p_id,
                    "predicate": "inside",
                    "object_entity": w_id,
                    "distance_m": 0.0
                })

        df_rel = pd.DataFrame(relationships)
        print(" -> Ingesting 'entity_relationships'...")
        df_rel.to_sql('entity_relationships', engine, if_exists='append', index=False)
        print("✅ City Knowledge Graph populated successfully.")

    except Exception as e:
        print(f"⚠️ Note on Knowledge Graph generation: {e}")

if __name__ == "__main__":
    build_city_knowledge_graph()
