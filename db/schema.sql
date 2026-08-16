-- NAGAR-X PostGIS Spatial Database Schema
-- Target Pilot Zone: Adivali-devad / Chikhale Sector (NAINA region, Navi Mumbai)

-- 0. Enable PostGIS and Cryptographic Extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1. Metadata Tracking Table (Data Provenance & Audit)
CREATE TABLE IF NOT EXISTS dataset_metadata (
    id SERIAL PRIMARY KEY,
    dataset_name VARCHAR(255) NOT NULL,
    source VARCHAR(255) NOT NULL,
    license VARCHAR(255),
    download_date DATE DEFAULT CURRENT_DATE,
    resolution VARCHAR(100),
    crs VARCHAR(50) DEFAULT 'EPSG:4326',
    confidence VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Administrative Areas (Wards, Sector Boundaries)
CREATE TABLE IF NOT EXISTS administrative_areas (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(100) DEFAULT 'ward',
    geometry GEOMETRY(MultiPolygon, 4326) NOT NULL,
    population INT DEFAULT 0,
    source VARCHAR(255) DEFAULT 'Census/Official',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_admin_geom ON administrative_areas USING GIST (geometry);

-- 3. Roads (Street Network Lines)
CREATE TABLE IF NOT EXISTS roads (
    id SERIAL PRIMARY KEY,
    road_class VARCHAR(100) DEFAULT 'residential',
    lanes INT DEFAULT 2,
    width_m NUMERIC(5,2) DEFAULT 7.0,
    speed_limit INT DEFAULT 40,
    capacity INT DEFAULT 1000,
    surface VARCHAR(50) DEFAULT 'asphalt',
    oneway BOOLEAN DEFAULT FALSE,
    geometry GEOMETRY(MultiLineString, 4326) NOT NULL,
    source VARCHAR(255) DEFAULT 'OpenStreetMap',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_roads_geom ON roads USING GIST (geometry);

-- 4. Routing Graph (Intersections & Edges for Shortest Path & Service Area Analysis)
CREATE TABLE IF NOT EXISTS road_nodes (
    id BIGINT PRIMARY KEY,
    geometry GEOMETRY(Point, 4326) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_road_nodes_geom ON road_nodes USING GIST (geometry);

CREATE TABLE IF NOT EXISTS road_edges (
    id SERIAL PRIMARY KEY,
    source_node BIGINT REFERENCES road_nodes(id) ON DELETE CASCADE,
    target_node BIGINT REFERENCES road_nodes(id) ON DELETE CASCADE,
    length_m NUMERIC(10,2) NOT NULL,
    travel_time_sec NUMERIC(10,2) NOT NULL,
    road_class VARCHAR(100),
    geometry GEOMETRY(LineString, 4326) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_road_edges_geom ON road_edges USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_road_edges_source ON road_edges(source_node);
CREATE INDEX IF NOT EXISTS idx_road_edges_target ON road_edges(target_node);

-- 5. Buildings (Footprints & Heights)
CREATE TABLE IF NOT EXISTS buildings (
    id SERIAL PRIMARY KEY,
    height_m NUMERIC(5,2) DEFAULT 9.0,
    floors INT DEFAULT 3,
    building_type VARCHAR(100) DEFAULT 'residential',
    land_use VARCHAR(100) DEFAULT 'mixed',
    confidence NUMERIC(3,2) DEFAULT 0.90,
    population_estimate INT DEFAULT 10,
    risk_score NUMERIC(3,2) DEFAULT 0.0,
    geometry GEOMETRY(MultiPolygon, 4326) NOT NULL,
    source VARCHAR(255) DEFAULT 'Google Open Buildings / OSM',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_buildings_geom ON buildings USING GIST (geometry);

-- 6. Facilities (Hospitals, Schools, Fire Stations, Police, Transit)
CREATE TABLE IF NOT EXISTS facilities (
    id SERIAL PRIMARY KEY,
    type VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    capacity INT DEFAULT 100,
    service_radius_m NUMERIC(8,2) DEFAULT 2000.0,
    geometry GEOMETRY(Geometry, 4326) NOT NULL,
    source VARCHAR(255) DEFAULT 'OpenStreetMap',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_facilities_geom ON facilities USING GIST (geometry);

-- 7. Population Zones (Demographic Grids)
CREATE TABLE IF NOT EXISTS population_zones (
    id SERIAL PRIMARY KEY,
    population INT DEFAULT 0,
    households INT DEFAULT 0,
    density_per_sqkm NUMERIC(10,2) DEFAULT 0.0,
    geometry GEOMETRY(Polygon, 4326) NOT NULL,
    source VARCHAR(255) DEFAULT 'Census Data/Derived Grid',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pop_zones_geom ON population_zones USING GIST (geometry);

-- 8. Candidate Development Land Parcels
CREATE TABLE IF NOT EXISTS land_parcels (
    id SERIAL PRIMARY KEY,
    land_use VARCHAR(100) DEFAULT 'unassigned',
    zoning VARCHAR(100) DEFAULT 'mixed_use',
    development_status VARCHAR(100) DEFAULT 'candidate',
    slope_deg NUMERIC(4,2) DEFAULT 0.0,
    elevation_m NUMERIC(6,2) DEFAULT 15.0,
    flood_risk NUMERIC(3,2) DEFAULT 0.0,
    geometry GEOMETRY(Polygon, 4326) NOT NULL,
    source VARCHAR(255) DEFAULT 'Synthetic Planning Partition',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_parcels_geom ON land_parcels USING GIST (geometry);

-- 9. Water Bodies (Rivers, Ponds, Streams)
CREATE TABLE IF NOT EXISTS water_bodies (
    id SERIAL PRIMARY KEY,
    type VARCHAR(100) DEFAULT 'river',
    seasonality VARCHAR(50) DEFAULT 'perennial',
    geometry GEOMETRY(MultiPolygon, 4326) NOT NULL,
    source VARCHAR(255) DEFAULT 'OpenStreetMap/Copernicus',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_water_geom ON water_bodies USING GIST (geometry);

-- 10. Planning Constraints (Environment Reserves, Exclusion Zones)
CREATE TABLE IF NOT EXISTS planning_constraints (
    id SERIAL PRIMARY KEY,
    type VARCHAR(100) NOT NULL, -- 'FLOOD_ZONE', 'CRZ', 'ECO_SENSITIVE'
    severity VARCHAR(50) DEFAULT 'HIGH',
    source VARCHAR(255) DEFAULT 'Planning Authority',
    geometry GEOMETRY(MultiPolygon, 4326) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_constraints_geom ON planning_constraints USING GIST (geometry);

-- 11. Scenarios & Scenario Changes
CREATE TABLE IF NOT EXISTS scenarios (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    base_version VARCHAR(50) DEFAULT 'v1.0',
    created_by VARCHAR(100) DEFAULT 'planner_admin',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scenario_changes (
    id SERIAL PRIMARY KEY,
    scenario_id INT REFERENCES scenarios(id) ON DELETE CASCADE,
    object_type VARCHAR(100) NOT NULL,
    object_id INT,
    operation VARCHAR(50) NOT NULL, -- 'INSERT', 'UPDATE', 'DELETE'
    parameters JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 12. Analysis Results Table
CREATE TABLE IF NOT EXISTS analysis_results (
    id SERIAL PRIMARY KEY,
    scenario_id INT REFERENCES scenarios(id) ON DELETE CASCADE,
    analysis_type VARCHAR(100) NOT NULL, -- 'MCDA_SITE_SUITABILITY', 'ACCESSIBILITY', 'SIMULATION'
    result_json JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 13. City Knowledge Graph: Entities & Relationships
CREATE TABLE IF NOT EXISTS spatial_entities (
    id VARCHAR(255) PRIMARY KEY,
    entity_type VARCHAR(100) NOT NULL, -- 'HOSPITAL', 'SCHOOL', 'POP_ZONE', 'ROAD', 'PARCEL', 'WARD'
    name VARCHAR(255),
    table_name VARCHAR(100),
    record_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS entity_relationships (
    id SERIAL PRIMARY KEY,
    subject_entity VARCHAR(255) REFERENCES spatial_entities(id) ON DELETE CASCADE,
    predicate VARCHAR(100) NOT NULL, -- 'serves', 'connects', 'located_in', 'near', 'inside'
    object_entity VARCHAR(255) REFERENCES spatial_entities(id) ON DELETE CASCADE,
    distance_m NUMERIC(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_rel_subject ON entity_relationships(subject_entity);
CREATE INDEX IF NOT EXISTS idx_rel_object ON entity_relationships(object_entity);
