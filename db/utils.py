import geopandas as gpd
from shapely.geometry import Polygon

# Standard Storage CRS (WGS84 - Global geographic CRS for GeoJSON & CesiumJS)
STORAGE_CRS = "EPSG:4326"

# Pre-Optimized Regional Bounding Boxes for 4 Urban Topologies
REGIONAL_BOUNDS = {
    # NAINA TPS-4 Boundary (Focus on Panvel bridge connectors)
    "adivali_devad": [
        (73.1300, 18.9900), (73.1500, 18.9900), (73.1500, 19.0050), (73.1300, 19.0050)
    ],
    # Target Logistics Zone (35 sq km safe extraction for heavy maritime infrastructure)
    "jnpt_port": [
        (72.9300, 18.9300), (73.0000, 18.9300), (73.0000, 18.9800), (72.9300, 18.9800)
    ],
    # Sector 17 & Surrounding Master-Planned Grid
    "chandigarh": [
        (76.7650, 30.7300), (76.7900, 30.7300), (76.7900, 30.7500), (76.7650, 30.7500)
    ],
    # Global Benchmark Port City (Industrial waterways and infrastructure)
    "rotterdam": [
        (4.4500, 51.8900), (4.5000, 51.8900), (4.5000, 51.9200), (4.4500, 51.9200)
    ]
}

def get_region_polygon(region_name: str) -> Polygon:
    """Returns the Shapely Polygon for a given region key."""
    key = region_name.lower().strip()
    if key not in REGIONAL_BOUNDS:
        raise ValueError(f"Unknown region: '{region_name}'. Valid options: {list(REGIONAL_BOUNDS.keys())}")
    return Polygon(REGIONAL_BOUNDS[key])

def ensure_crs(gdf: gpd.GeoDataFrame, target_crs: str = STORAGE_CRS) -> gpd.GeoDataFrame:
    """Ensures GeoDataFrame is assigned CRS and reprojected to target_crs."""
    if gdf.crs is None:
        gdf = gdf.set_crs(STORAGE_CRS)
    if gdf.crs.to_string() != target_crs:
        gdf = gdf.to_crs(target_crs)
    return gdf

def get_utm_projected_gdf(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Dynamically estimates and projects the GeoDataFrame to its optimal local UTM Zone
    (e.g., UTM 43N for India, UTM 31N for Europe/Rotterdam) for precise metric calculations.
    """
    gdf_wgs84 = ensure_crs(gdf, STORAGE_CRS)
    estimated_utm = gdf_wgs84.estimate_utm_crs()
    return gdf_wgs84.to_crs(estimated_utm)

def calculate_metric_area_sqm(gdf: gpd.GeoDataFrame) -> gpd.GeoSeries:
    """Calculates metric area (sq meters) using dynamic local UTM projection."""
    proj_gdf = get_utm_projected_gdf(gdf)
    return proj_gdf.geometry.area

def calculate_metric_length_m(gdf: gpd.GeoDataFrame) -> gpd.GeoSeries:
    """Calculates metric length (meters) using dynamic local UTM projection."""
    proj_gdf = get_utm_projected_gdf(gdf)
    return proj_gdf.geometry.length
