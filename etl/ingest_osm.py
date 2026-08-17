"""Real OpenStreetMap ingestion for the pilot sector. ARCHITECTURE §8, §26.

Design rule: this pipeline NEVER silently substitutes synthetic data for real
data. If a layer cannot be fetched it is reported as a failure and the row
count stays zero. The previous db/etl/fetch_osm.py wrapped every query in a
bare `except` that fell back to hardcoded points, so a total Overpass outage
still produced a "successful" run with invented hospitals.

Usage:
    python -m etl.ingest_osm                 # pilot bbox
    python -m etl.ingest_osm --scale 3       # widen the bbox 3x
    python -m etl.ingest_osm --dry-run       # fetch and report, write nothing
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import warnings
from dataclasses import dataclass, field
from datetime import date
from typing import Any

warnings.filterwarnings("ignore")

import geopandas as gpd
import osmnx as ox
import pandas as pd
from shapely.geometry import MultiLineString, MultiPolygon, box
from sqlalchemy import text

STORAGE_CRS = "EPSG:4326"
PROJECTED_CRS = "EPSG:32643"          # UTM 43N - Navi Mumbai
PILOT_BBOX = (73.13, 18.99, 73.15, 19.005)   # Adivali-devad, NAINA

# Tables this pipeline owns, in FK-safe truncation order.
OWNED_TABLES = ["buildings", "facilities", "roads", "water_bodies",
                "land_parcels", "population_zones"]


@dataclass
class LayerReport:
    name: str
    fetched: int = 0
    written: int = 0
    status: str = "pending"      # ok | empty | failed | skipped
    detail: str = ""


@dataclass
class Report:
    layers: list[LayerReport] = field(default_factory=list)

    def add(self, r: LayerReport) -> LayerReport:
        self.layers.append(r)
        return r

    def ok(self) -> bool:
        return all(l.status in ("ok", "skipped") for l in self.layers)

    def render(self) -> str:
        w = max(len(l.name) for l in self.layers) if self.layers else 10
        out = ["", "=" * 68, "  OSM INGESTION REPORT", "=" * 68,
               f"  {'layer'.ljust(w)}  {'fetched':>8}  {'written':>8}  status"]
        for l in self.layers:
            out.append(f"  {l.name.ljust(w)}  {l.fetched:>8}  {l.written:>8}  "
                       f"{l.status}{('  ' + l.detail) if l.detail else ''}")
        out.append("=" * 68)
        return "\n".join(out)


def scaled_bbox(scale: float) -> tuple[float, float, float, float]:
    minx, miny, maxx, maxy = PILOT_BBOX
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    hw, hh = (maxx - minx) / 2 * scale, (maxy - miny) / 2 * scale
    return (cx - hw, cy - hh, cx + hw, cy + hh)


def _multi(gdf: gpd.GeoDataFrame, kind: str) -> gpd.GeoDataFrame:
    """Coerce to Multi* because the schema declares MULTI geometry columns."""
    if kind == "polygon":
        keep = gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])
        gdf = gdf[keep].copy()
        gdf["geometry"] = gdf.geometry.apply(
            lambda g: g if g.geom_type == "MultiPolygon" else MultiPolygon([g]))
    else:
        keep = gdf.geometry.geom_type.isin(["LineString", "MultiLineString"])
        gdf = gdf[keep].copy()
        gdf["geometry"] = gdf.geometry.apply(
            lambda g: g if g.geom_type == "MultiLineString"
            else MultiLineString([g]))
    return gdf


def _single_polygon(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Explode to single POLYGON.

    land_parcels and population_zones declare POLYGON, not MULTIPOLYGON, so a
    MultiPolygon insert is rejected outright. Explode rather than take the
    largest ring: every real part stays in the dataset.
    """
    keep = gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])
    gdf = gdf[keep].explode(index_parts=False).reset_index(drop=True)
    return gdf[gdf.geometry.geom_type == "Polygon"]


def _clean(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Drop null/invalid geometry.

    buffer(0) is the classic polygon-repair trick, but applied to a LineString
    it returns an EMPTY POLYGON - silently deleting every road. Repair only
    the (multi)polygons and leave lines and points untouched.
    """
    gdf = gdf[~gdf.geometry.isna()].copy()
    is_poly = gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])
    if is_poly.any():
        gdf.loc[is_poly, "geometry"] = gdf.loc[is_poly, "geometry"].buffer(0)
    return gdf[gdf.geometry.is_valid & ~gdf.geometry.is_empty]


FLOOR_HEIGHT_M = 3.2

# Typical storey counts by OSM building type for Indian peri-urban fabric.
TYPICAL_FLOORS: dict[str, int] = {
    "apartments": 7, "residential": 4, "house": 2, "detached": 2,
    "bungalow": 2, "hut": 1, "shed": 1, "garage": 1, "garages": 1,
    "roof": 1, "carport": 1, "commercial": 4, "retail": 3, "office": 6,
    "supermarket": 2, "mall": 4, "industrial": 2, "warehouse": 2,
    "factory": 2, "manufacture": 2, "hospital": 5, "school": 3,
    "college": 4, "university": 5, "hotel": 6, "train_station": 2,
    "civic": 3, "government": 4, "public": 3, "temple": 2, "mosque": 2,
    "church": 2, "religious": 2, "shrine": 1, "construction": 3, "yes": 3,
}


def _tag_num(v: Any) -> float | None:
    """Parse a numeric OSM tag, tolerating units and rejecting junk.

    Live data contains height="Suyash Society" and height="0"; both must be
    discarded rather than silently becoming a zero-height building.
    """
    if v is None:
        return None
    s = str(v).strip().lower()
    for unit in ("meters", "metres", "m"):
        if s.endswith(unit):
            s = s[: -len(unit)].strip()
            break
    try:
        return float(s)
    except ValueError:
        return None


def _jitter(key: Any, lo: float, hi: float) -> float:
    """Deterministic per-building factor so one type is not a row of clones."""
    h = int(hashlib.md5(str(key).encode()).hexdigest()[:8], 16)
    return lo + (h % 1000) / 1000.0 * (hi - lo)


def _first(v: Any, default: Any) -> Any:
    if isinstance(v, list):
        v = v[0] if v else default
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return default
    return v


# ----------------------------------------------------------------- layers
def ingest_roads(poly, engine, rep: Report, dry: bool) -> None:
    r = rep.add(LayerReport("roads"))
    try:
        G = ox.graph_from_polygon(poly, network_type="all")
        _, edges = ox.graph_to_gdfs(G)
    except Exception as e:
        r.status, r.detail = "failed", f"{type(e).__name__}: {str(e)[:60]}"
        return
    r.fetched = len(edges)
    if edges.empty:
        r.status = "empty"
        return

    speeds = {"motorway": 80, "trunk": 60, "primary": 50, "secondary": 40,
              "tertiary": 40, "residential": 30, "service": 20,
              "unclassified": 30, "living_street": 20, "footway": 5,
              "path": 5, "track": 20}
    df = pd.DataFrame(index=edges.index)
    df["road_class"] = edges.get("highway", "residential").apply(
        lambda v: str(_first(v, "residential")))
    df["lanes"] = edges.get("lanes", pd.Series(index=edges.index)).apply(
        lambda v: int(_first(v, 2)) if str(_first(v, 2)).isdigit() else 2)
    df["width_m"] = 7.0
    df["speed_limit"] = df["road_class"].map(speeds).fillna(30).astype(int)
    df["capacity"] = df["lanes"] * 600
    df["surface"] = edges.get("surface", pd.Series(index=edges.index)).apply(
        lambda v: str(_first(v, "asphalt")))
    df["oneway"] = edges.get("oneway", pd.Series(index=edges.index)).apply(
        lambda v: bool(_first(v, False)))
    df["geometry"] = edges["geometry"].values
    df["source"] = "OpenStreetMap"

    g = _multi(_clean(gpd.GeoDataFrame(df, geometry="geometry",
                                       crs=STORAGE_CRS)), "line")
    if not dry:
        g.to_postgis("roads", engine, if_exists="append", index=False)
    r.written, r.status = len(g), "ok"


def ingest_facilities(poly, engine, rep: Report, dry: bool) -> None:
    r = rep.add(LayerReport("facilities"))
    tags = {"amenity": ["hospital", "clinic", "school", "fire_station",
                        "police", "doctors", "college", "university"]}
    try:
        gdf = ox.features_from_polygon(poly, tags)
    except Exception as e:
        # InsufficientResponseError means "nothing mapped here", not a bug.
        r.status = "empty" if "Insufficient" in type(e).__name__ else "failed"
        r.detail = ("no civic amenities mapped in this bbox - widen with --scale"
                    if r.status == "empty" else f"{type(e).__name__}")
        return
    r.fetched = len(gdf)
    if gdf.empty:
        r.status = "empty"
        return

    caps = {"hospital": 150, "clinic": 50, "school": 300, "college": 800,
            "university": 2000, "fire_station": 30, "police": 40, "doctors": 20}
    radii = {"hospital": 3000.0, "clinic": 1500.0, "school": 2000.0,
             "college": 5000.0, "university": 8000.0, "fire_station": 4000.0,
             "police": 4000.0, "doctors": 1000.0}

    gdf = _clean(gdf.to_crs(STORAGE_CRS))
    rows = []
    for _, row in gdf.iterrows():
        t = str(_first(row.get("amenity"), "clinic"))
        name = str(_first(row.get("name"), f"Unnamed {t}"))
        geom = row.geometry
        # Schema stores facilities as POINT; polygons become their centroid.
        if geom.geom_type != "Point":
            geom = geom.centroid
        rows.append({"type": t, "name": name[:255],
                     "capacity": caps.get(t, 50),
                     "service_radius_m": radii.get(t, 2000.0),
                     "geometry": geom, "source": "OpenStreetMap"})
    g = gpd.GeoDataFrame(rows, geometry="geometry", crs=STORAGE_CRS)
    if not dry:
        g.to_postgis("facilities", engine, if_exists="append", index=False)
    r.written, r.status = len(g), "ok"


def ingest_buildings(poly, engine, rep: Report, dry: bool) -> None:
    r = rep.add(LayerReport("buildings"))
    try:
        gdf = ox.features_from_polygon(poly, {"building": True})
    except Exception as e:
        r.status = "empty" if "Insufficient" in type(e).__name__ else "failed"
        r.detail = f"{type(e).__name__}"
        return
    r.fetched = len(gdf)
    if gdf.empty:
        r.status = "empty"
        return

    gdf = _clean(gdf.to_crs(STORAGE_CRS))
    gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
    if gdf.empty:
        r.status = "empty"
        return

    def _levels(v: Any) -> int:
        """Clamp to a sane storey count.

        Real OSM contains typos like building:levels=3715, which produced an
        11,888 m tall building and overflowed numeric(5,2). Trusting raw tags
        is not an option on live data.
        """
        try:
            n = int(float(_first(v, 2)))
        except (TypeError, ValueError):
            return 2
        return min(max(n, 1), 163)          # Burj Khalifa = 163 storeys

    # Footprint area drives the population estimate; compute it in metres.
    area_m2 = gdf.to_crs(PROJECTED_CRS).geometry.area

    # --- height model ---------------------------------------------------
    # Only ~1.7% of buildings here carry building:levels or height, so a
    # bare default made 98% of the city an identical 2-storey block. Use
    # real tags where they exist, then fall back to a typology + footprint
    # model with deterministic per-building variation.
    # Positional access: osmnx indexes by (element_type, osmid) and those
    # labels can repeat, so .get(label) may return a Series instead of a
    # scalar. Iterating by position keeps every lookup unambiguous.
    def _col(name: str) -> list[Any]:
        if name in gdf.columns:
            return list(gdf[name].values)
        return [None] * len(gdf)

    levels_col = _col("building:levels")
    height_col = _col("height")
    roof_col = _col("roof:levels")
    type_col = _col("building")
    osmid_col = list(gdf.index)

    heights: list[float] = []
    floors_list: list[int] = []
    for i, area in enumerate(area_m2.values):
        idx = osmid_col[i]
        h = _tag_num(_first(height_col[i], None))
        if h is not None and 1.5 <= h <= 999.0:
            heights.append(round(h, 2))
            floors_list.append(max(1, int(round(h / FLOOR_HEIGHT_M))))
            continue

        lv = _tag_num(_first(levels_col[i], None))
        if lv is not None and 1 <= lv <= 163:
            fl = int(lv)
            roof = _tag_num(_first(roof_col[i], None)) or 0.0
            heights.append(round(min((fl + min(roof, 3.0)) * FLOOR_HEIGHT_M,
                                     999.0), 2))
            floors_list.append(fl)
            continue

        btype = str(_first(type_col[i], "yes")).lower()
        base = TYPICAL_FLOORS.get(btype, TYPICAL_FLOORS["yes"])
        a = float(area)
        if a < 30:
            base = min(base, 1)
        elif a < 60:
            base = min(base, 2)
        elif a < 120:
            base = min(base, 3)
        elif a > 2000:
            base = max(base, 4)
        fl = max(1, min(int(round(base * _jitter(idx, 0.75, 1.35))), 40))
        heights.append(round(fl * FLOOR_HEIGHT_M, 2))
        floors_list.append(fl)

    floors = pd.Series(floors_list, index=gdf.index)
    height_m = pd.Series(heights, index=gdf.index)

    out = gpd.GeoDataFrame({
        # numeric(5,2) in the schema -> hard ceiling at 999.99 m
        "height_m": height_m.clip(upper=999.0).astype(float),
        "floors": floors.astype(int),
        "building_type": gdf.get("building", "yes").apply(
            lambda v: str(_first(v, "yes"))),
        "land_use": "mixed",
        "confidence": 0.9,
        # ~20 m2 of floor space per person, capped to stay plausible.
        "population_estimate": ((area_m2 * floors) / 20.0
                                ).clip(0, 5000).round().astype(int).values,
        "risk_score": 0.0,
        "geometry": gdf.geometry.values,
        "source": "OpenStreetMap",
    }, geometry="geometry", crs=STORAGE_CRS)
    out = _multi(out, "polygon")
    if not dry:
        out.to_postgis("buildings", engine, if_exists="append", index=False)
    r.written, r.status = len(out), "ok"


def ingest_water(poly, engine, rep: Report, dry: bool) -> None:
    r = rep.add(LayerReport("water_bodies"))
    try:
        gdf = ox.features_from_polygon(poly, {"natural": ["water"]})
    except Exception as e:
        r.status = "empty" if "Insufficient" in type(e).__name__ else "failed"
        return
    r.fetched = len(gdf)
    gdf = _clean(gdf.to_crs(STORAGE_CRS))
    gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
    if gdf.empty:
        r.status = "empty"
        return
    out = gpd.GeoDataFrame({
        "type": gdf.get("water", "lake").apply(lambda v: str(_first(v, "lake"))),
        "seasonality": "perennial",
        "geometry": gdf.geometry.values,
        "source": "OpenStreetMap",
    }, geometry="geometry", crs=STORAGE_CRS)
    out = _multi(out, "polygon")
    if not dry:
        out.to_postgis("water_bodies", engine, if_exists="append", index=False)
    r.written, r.status = len(out), "ok"


def ingest_landuse_parcels(poly, engine, rep: Report, dry: bool) -> None:
    """Land parcels from OSM landuse polygons - real geometry, derived attributes."""
    r = rep.add(LayerReport("land_parcels"))
    try:
        gdf = ox.features_from_polygon(poly, {"landuse": True})
    except Exception as e:
        r.status = "empty" if "Insufficient" in type(e).__name__ else "failed"
        return
    r.fetched = len(gdf)
    gdf = _clean(gdf.to_crs(STORAGE_CRS))
    gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
    if gdf.empty:
        r.status = "empty"
        return

    zoning = {"residential": "R1", "commercial": "C1", "industrial": "I1",
              "farmland": "AG", "forest": "GR", "grass": "GR",
              "retail": "C2", "construction": "R2"}
    lu = gdf.get("landuse", "residential").apply(
        lambda v: str(_first(v, "residential")))
    out = gpd.GeoDataFrame({
        "land_use": lu.values,
        "zoning": lu.map(zoning).fillna("R1").values,
        "development_status": "vacant",
        "slope_deg": 2.0,
        "elevation_m": 20.0,
        "flood_risk": 0.1,
        "geometry": gdf.geometry.values,
        "source": "OpenStreetMap",
    }, geometry="geometry", crs=STORAGE_CRS)
    out = _single_polygon(out)
    if not dry:
        out.to_postgis("land_parcels", engine, if_exists="append", index=False)
    r.written, r.status = len(out), "ok"


def derive_population_zones(engine, rep: Report, dry: bool) -> None:
    """Population zones aggregated from ingested building estimates.

    Derived from real footprints rather than invented: each administrative
    grid cell sums the population of the buildings inside it.
    """
    r = rep.add(LayerReport("population_zones"))
    if dry:
        r.status, r.detail = "skipped", "dry-run"
        return
    sql = text("""
        INSERT INTO population_zones
            (population, households, density_per_sqkm, geometry, source)
        SELECT
            SUM(b.population_estimate)::int,
            (SUM(b.population_estimate) / 4.5)::int,
            (SUM(b.population_estimate) /
             NULLIF(ST_Area(g.cell::geography) / 1000000.0, 0))::numeric(12,2),
            g.cell,
            'derived:buildings'
        FROM (
            -- ST_SquareGrid returns SRID 0; restore 4326 or ST_Intersects
            -- fails with "Operation on mixed SRID geometries".
            SELECT ST_SetSRID(
                     (ST_SquareGrid(0.005,
                        ST_Extent(geometry)::geometry)).geom, 4326) AS cell
            FROM buildings
        ) g
        JOIN buildings b ON ST_Intersects(b.geometry, g.cell)
        GROUP BY g.cell
        HAVING SUM(b.population_estimate) > 0
    """)
    with engine.begin() as conn:
        res = conn.execute(sql)
        r.written = res.rowcount or 0
    r.fetched = r.written
    r.status = "ok" if r.written else "empty"


# ------------------------------------------------------------------ main
def main() -> int:
    ap = argparse.ArgumentParser(description="Ingest real OSM data into PostGIS")
    ap.add_argument("--scale", type=float, default=1.0,
                    help="widen the pilot bbox by this factor (default 1.0)")
    ap.add_argument("--dry-run", action="store_true",
                    help="fetch and report without writing")
    ap.add_argument("--keep", action="store_true",
                    help="append instead of truncating owned tables first")
    args = ap.parse_args()

    sys.path.insert(0, "backend")
    from app.storage.db import get_engine

    engine = get_engine()
    bounds = scaled_bbox(args.scale)
    poly = box(*bounds)

    print(f"bbox      {tuple(round(v, 4) for v in bounds)}  (scale {args.scale}x)")
    print(f"mode      {'DRY RUN - no writes' if args.dry_run else 'writing to PostGIS'}")

    if not args.dry_run and not args.keep:
        with engine.begin() as conn:
            conn.execute(text(
                f"TRUNCATE TABLE {', '.join(OWNED_TABLES)} RESTART IDENTITY CASCADE"))
        print(f"truncated {', '.join(OWNED_TABLES)}")

    rep = Report()
    ingest_roads(poly, engine, rep, args.dry_run)
    ingest_facilities(poly, engine, rep, args.dry_run)
    ingest_buildings(poly, engine, rep, args.dry_run)
    ingest_water(poly, engine, rep, args.dry_run)
    ingest_landuse_parcels(poly, engine, rep, args.dry_run)
    derive_population_zones(engine, rep, args.dry_run)

    if not args.dry_run:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO dataset_metadata
                    (dataset_name, source, license, download_date, resolution,
                     crs, confidence)
                VALUES ('OpenStreetMap Base Layers',
                        'OpenStreetMap Foundation', 'ODbL 1.0', :d,
                        'Vector topology', 'EPSG:4326', 'High')
            """), {"d": date.today()})

    print(rep.render())
    failed = [l.name for l in rep.layers if l.status == "failed"]
    empty = [l.name for l in rep.layers if l.status == "empty"]
    if failed:
        print(f"\n  FAILED layers: {', '.join(failed)}")
        print("  No synthetic data was substituted. Re-run to retry.")
    if empty:
        print(f"\n  EMPTY layers: {', '.join(empty)}")
        print("  OSM has nothing mapped there. Try --scale 3 for a wider area.")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
