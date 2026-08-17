import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import geopandas as gpd
from shapely.geometry import Polygon
from utils import (
    STORAGE_CRS,
    REGIONAL_BOUNDS,
    get_region_polygon,
    ensure_crs,
    get_utm_projected_gdf,
    calculate_metric_area_sqm,
    calculate_metric_length_m
)

# For backward compatibility
PROJECTED_CRS = "EPSG:32643"
ADIVALI_DEVAD_BOUNDS = REGIONAL_BOUNDS["adivali_devad"]

def get_pilot_sector_polygon():
    """Returns the Shapely Polygon for the Adivali-devad pilot sector."""
    return get_region_polygon("adivali_devad")
