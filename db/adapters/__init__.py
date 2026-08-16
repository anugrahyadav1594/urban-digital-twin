"""Adapter layer: PostGIS schema <-> deterministic engine contracts.

ARCHITECTURE §5.3, §8, §12. The engines stay pure and database-agnostic; this
package owns every translation between the two.
"""
from .geometry import (
    ANALYSIS_SRID, STORAGE_SRID, as_linestring, as_point, as_polygon,
    assert_projected, explode_lines, repair, to_analysis, to_storage,
)
from .loaders import (
    load_buildings, load_city, load_constraints, load_facilities,
    load_parcels, load_population_zones, load_roads,
)
from .vocab import (
    normalize_facility_type, normalize_land_use, normalize_road_class,
    normalize_severity, zoning_permits,
)
from .writers import (
    list_results, load_result, result_to_geojson, save_result,
)

__all__ = [
    "ANALYSIS_SRID", "STORAGE_SRID", "as_linestring", "as_point", "as_polygon",
    "assert_projected", "explode_lines", "repair", "to_analysis", "to_storage",
    "load_buildings", "load_city", "load_constraints", "load_facilities",
    "load_parcels", "load_population_zones", "load_roads",
    "normalize_facility_type", "normalize_land_use", "normalize_road_class",
    "normalize_severity", "zoning_permits",
    "list_results", "load_result", "result_to_geojson", "save_result",
]
