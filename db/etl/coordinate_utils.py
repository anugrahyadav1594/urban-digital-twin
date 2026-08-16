import geopandas as gpd
from shapely.geometry import Polygon

# Standard Coordinate Reference Systems
STORAGE_CRS = "EPSG:4326"   # WGS84 - Global geographic CRS for GeoJSON & CesiumJS
PROJECTED_CRS = "EPSG:32643" # UTM Zone 43N - Metric projected CRS for Western India (Navi Mumbai)

# Adivali-devad / Chikhale Pilot Zone Bounding Polygon
ADIVALI_DEVAD_BOUNDS = [
    (73.1300, 18.9900),
    (73.1500, 18.9900),
    (73.1500, 19.0050),
    (73.1300, 19.0050)
]

def get_pilot_sector_polygon():
    """Returns the Shapely Polygon for the Adivali-devad pilot sector."""
    return Polygon(ADIVALI_DEVAD_BOUNDS)

def ensure_crs(gdf: gpd.GeoDataFrame, target_crs: str = STORAGE_CRS) -> gpd.GeoDataFrame:
    """
    Ensures that the GeoDataFrame is reprojected to the target CRS.
    """
    if gdf.crs is None:
        gdf = gdf.set_crs(STORAGE_CRS)
    if gdf.crs.to_string() != target_crs:
        gdf = gdf.to_crs(target_crs)
    return gdf

def calculate_metric_area_sqm(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Computes accurate metric area in square meters using projected UTM Zone 43N.
    """
    temp_gdf = ensure_crs(gdf, PROJECTED_CRS)
    return temp_gdf.geometry.area

def calculate_metric_length_m(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Computes accurate metric length in meters using projected UTM Zone 43N.
    """
    temp_gdf = ensure_crs(gdf, PROJECTED_CRS)
    return temp_gdf.geometry.length
