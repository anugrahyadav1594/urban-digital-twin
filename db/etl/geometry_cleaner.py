import geopandas as gpd
from shapely.validation import make_valid
from shapely.geometry import MultiPolygon, Polygon, MultiLineString, LineString

def clean_geometries(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Cleans spatial geometries in a GeoDataFrame:
    1. Removes empty geometries.
    2. Fixes invalid geometries using Shapely make_valid.
    3. Removes duplicate geometries.
    4. Drops unencodable list/dict columns that PostGIS cannot accept.
    """
    if gdf.empty:
        return gdf

    # 1. Remove empty geometries
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notnull()].copy()

    # 2. Fix invalid geometries
    gdf['geometry'] = gdf['geometry'].apply(lambda geom: make_valid(geom) if not geom.is_valid else geom)

    # 3. Drop duplicate geometries
    gdf = gdf.drop_duplicates(subset=['geometry']).copy()

    # 4. Clean column types for SQL compatibility
    cols_to_drop = []
    for col in gdf.columns:
        if col == 'geometry':
            continue
        first_val = gdf[col].dropna().iloc[0] if not gdf[col].dropna().empty else None
        if isinstance(first_val, (list, dict)):
            cols_to_drop.append(col)

    if cols_to_drop:
        gdf = gdf.drop(columns=cols_to_drop)

    return gdf

def force_multi_polygon(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Ensures polygon geometries are cast to MultiPolygon for schema uniformity."""
    def to_multi(geom):
        if isinstance(geom, Polygon):
            return MultiPolygon([geom])
        elif isinstance(geom, MultiPolygon):
            return geom
        return geom
    gdf['geometry'] = gdf['geometry'].apply(to_multi)
    return gdf

def force_multi_linestring(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Ensures line geometries are cast to MultiLineString for schema uniformity."""
    def to_multi(geom):
        if isinstance(geom, LineString):
            return MultiLineString([geom])
        elif isinstance(geom, MultiLineString):
            return geom
        return geom
    gdf['geometry'] = gdf['geometry'].apply(to_multi)
    return gdf
