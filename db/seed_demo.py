#!/usr/bin/env python3
"""Offline-first PostGIS seed script for the NagarX pilot sector.

Loads real OpenStreetMap features from the repository's checked-in Overpass JSON
caches (`cache/*.json` and `db/cache/*.json` within the Navi Mumbai / New Panvel /
Kalundre River / NAINA corridor) directly into PostGIS — no live Overpass API
calls required, so seeding completes deterministically in seconds without
network timeouts or OSMnx cache-hash mismatches across Python/OSMnx versions.

Usage (from repository root):
    .venv/bin/python db/seed_demo.py
    .venv/bin/python db/seed_demo.py --dry-run
    make seed
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Geographic filter for Navi Mumbai / New Panvel / Kalundre / NAINA caches
BBOX_LON = (73.07, 73.205)
BBOX_LAT = (18.96, 19.06)

OWNED_TABLES = [
    "buildings",
    "facilities",
    "roads",
    "water_bodies",
    "land_parcels",
    "population_zones",
]

ROAD_SPEEDS: dict[str, int] = {
    "motorway": 80,
    "motorway_link": 50,
    "trunk": 60,
    "trunk_link": 45,
    "primary": 50,
    "primary_link": 40,
    "secondary": 40,
    "secondary_link": 35,
    "tertiary": 35,
    "tertiary_link": 30,
    "residential": 30,
    "unclassified": 30,
    "living_street": 20,
    "service": 20,
    "track": 20,
    "pedestrian": 10,
    "footway": 5,
    "path": 5,
}

EXCLUDED_HIGHWAYS = {
    "proposed",
    "construction",
    "abandoned",
    "razed",
    "platform",
    "corridor",
    "steps",
    "escalator",
}

TYPICAL_FLOORS: dict[str, int] = {
    "apartments": 7,
    "residential": 4,
    "house": 2,
    "detached": 2,
    "bungalow": 2,
    "hut": 1,
    "shed": 1,
    "garage": 1,
    "garages": 1,
    "roof": 1,
    "carport": 1,
    "commercial": 4,
    "retail": 3,
    "office": 6,
    "supermarket": 2,
    "mall": 4,
    "industrial": 2,
    "warehouse": 2,
    "factory": 2,
    "hospital": 5,
    "school": 3,
    "college": 4,
    "university": 5,
    "hotel": 6,
    "train_station": 2,
    "civic": 3,
    "government": 4,
    "public": 3,
    "temple": 2,
    "mosque": 2,
    "church": 2,
    "religious": 2,
    "shrine": 1,
    "yes": 3,
}

FACILITY_AMENITIES = {
    "hospital",
    "clinic",
    "doctors",
    "pharmacy",
    "school",
    "college",
    "university",
    "fire_station",
    "police",
}

FLOOR_HEIGHT_M = 3.2


def _in_study_region(lon: float, lat: float) -> bool:
    return BBOX_LON[0] <= lon <= BBOX_LON[1] and BBOX_LAT[0] <= lat <= BBOX_LAT[1]


def _parse_int(val: Any, default: int) -> int:
    if val is None:
        return default
    s = str(val).strip().split(";")[0].split()[0]
    try:
        n = int(float(s))
        return n if n > 0 else default
    except ValueError:
        return default


def _parse_float(val: Any) -> float | None:
    if val is None:
        return None
    s = str(val).strip().lower()
    for unit in ("meters", "metres", "km/h", "kmh", "m"):
        if s.endswith(unit):
            s = s[: -len(unit)].strip()
            break
    try:
        n = float(s)
        return n if n > 0 else None
    except ValueError:
        return None


def _is_oneway(tags: dict[str, Any], highway: str) -> bool:
    raw = str(tags.get("oneway", "")).strip().lower()
    if raw in ("yes", "true", "1"):
        return True
    if raw in ("no", "false", "0"):
        return False
    return highway in ("motorway", "motorway_link")


def _det_jitter(seed_key: Any, lo: float, hi: float) -> float:
    h = int(hashlib.md5(str(seed_key).encode("utf-8")).hexdigest()[:8], 16)
    return lo + (h % 1000) / 1000.0 * (hi - lo)


def _linestring_wkt(coords: list[tuple[float, float]]) -> str | None:
    dedup: list[tuple[float, float]] = []
    for pt in coords:
        if not dedup or pt != dedup[-1]:
            dedup.append(pt)
    if len(dedup) < 2:
        return None
    body = ", ".join(f"{lon:.7f} {lat:.7f}" for lon, lat in dedup)
    return f"LINESTRING({body})"


def _polygon_wkt(coords: list[tuple[float, float]]) -> str | None:
    ring: list[tuple[float, float]] = []
    for pt in coords:
        if not ring or pt != ring[-1]:
            ring.append(pt)
    if len(ring) < 3:
        return None
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    if len(ring) < 4:
        return None
    body = ", ".join(f"{lon:.7f} {lat:.7f}" for lon, lat in ring)
    return f"POLYGON(({body}))"


def _approx_poly_area_m2(coords: list[tuple[float, float]]) -> float:
    """Fast local planar shoelace area in m^2 at ~19 deg N."""
    if len(coords) < 3:
        return 0.0
    m_per_deg_lat = 110_690.0
    m_per_deg_lon = 104_950.0
    x0, y0 = coords[0]
    pts = [((x - x0) * m_per_deg_lon, (y - y0) * m_per_deg_lat) for x, y in coords]
    area2 = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        area2 += x1 * y2 - x2 * y1
    return abs(area2) * 0.5


def collect_cached_osm() -> dict[str, list[dict[str, Any]]]:
    """Read and deduplicate cached Overpass JSON elements in the study corridor."""
    cache_files = sorted(glob.glob(str(REPO_ROOT / "cache" / "*.json"))) + sorted(
        glob.glob(str(REPO_ROOT / "db" / "cache" / "*.json"))
    )
    if not cache_files:
        raise FileNotFoundError(
            f"No cached Overpass JSON files found under {REPO_ROOT / 'cache'}."
        )

    nodes: dict[int, tuple[float, float]] = {}
    tagged_nodes: dict[int, dict[str, Any]] = {}
    ways: dict[int, dict[str, Any]] = {}

    for path in cache_files:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except Exception:
            continue
        elements = payload.get("elements")
        if not isinstance(elements, list) or not elements:
            continue

        # Check whether this cache file belongs to the Panvel / NAINA region
        sample_coords = [
            (float(e["lon"]), float(e["lat"]))
            for e in elements[:200]
            if e.get("type") == "node" and "lon" in e and "lat" in e
        ]
        if sample_coords and not any(_in_study_region(lon, lat) for lon, lat in sample_coords):
            continue

        for el in elements:
            etype = el.get("type")
            eid = el.get("id")
            if eid is None:
                continue
            if etype == "node" and "lon" in el and "lat" in el:
                lon, lat = float(el["lon"]), float(el["lat"])
                if _in_study_region(lon, lat):
                    nodes[int(eid)] = (lon, lat)
                    if el.get("tags"):
                        tagged_nodes[int(eid)] = el
            elif etype == "way" and el.get("nodes"):
                if int(eid) not in ways or len(el.get("tags", {})) > len(
                    ways[int(eid)].get("tags", {})
                ):
                    ways[int(eid)] = el

    roads_rows: list[dict[str, Any]] = []
    buildings_rows: list[dict[str, Any]] = []
    facilities_rows: list[dict[str, Any]] = []
    water_rows: list[dict[str, Any]] = []
    parcel_rows: list[dict[str, Any]] = []
    seen_facilities: set[str] = set()

    # Facility point nodes
    for nid, el in sorted(tagged_nodes.items()):
        tags = el.get("tags") or {}
        amenity = tags.get("amenity") or tags.get("healthcare") or tags.get("emergency")
        if amenity not in FACILITY_AMENITIES:
            continue
        lon, lat = nodes[nid]
        key = f"node:{nid}"
        if key in seen_facilities:
            continue
        seen_facilities.add(key)
        ftype = "hospital" if amenity in ("clinic", "doctors") else str(amenity)
        name = str(tags.get("name") or tags.get("name:en") or f"{ftype.title()} #{nid}")[:250]
        facilities_rows.append(
            {
                "type": ftype[:95],
                "name": name,
                "capacity": 200 if ftype == "hospital" else 120,
                "service_radius_m": 3000.0 if ftype in ("hospital", "fire_station") else 1800.0,
                "lon": lon,
                "lat": lat,
                "source": f"OpenStreetMap:node/{nid}",
            }
        )

    # Ways (roads, buildings, closed-way facilities, water bodies, landuse parcels)
    for wid, way in sorted(ways.items()):
        tags = way.get("tags") or {}
        coords = [nodes[nid] for nid in way.get("nodes", []) if nid in nodes]
        if len(coords) < 2:
            continue

        # 1. Roads
        hw = tags.get("highway")
        if hw:
            hw_str = str(hw[0] if isinstance(hw, list) else hw).strip().lower()
            if hw_str and hw_str not in EXCLUDED_HIGHWAYS:
                wkt = _linestring_wkt(coords)
                if wkt:
                    lanes = max(1, min(8, _parse_int(tags.get("lanes"), 2)))
                    parsed_speed = _parse_float(tags.get("maxspeed"))
                    speed_limit = int(
                        parsed_speed if parsed_speed else ROAD_SPEEDS.get(hw_str, 30)
                    )
                    roads_rows.append(
                        {
                            "road_class": hw_str[:95],
                            "lanes": lanes,
                            "width_m": round(max(3.5, lanes * 3.5), 2),
                            "speed_limit": max(5, min(120, speed_limit)),
                            "capacity": lanes * 600,
                            "surface": str(tags.get("surface") or "asphalt")[:48],
                            "oneway": _is_oneway(tags, hw_str),
                            "wkt": wkt,
                            "source": f"OpenStreetMap:osm_way_{wid}",
                        }
                    )

        # 2. Facility polygons -> centroid point
        amenity = tags.get("amenity") or tags.get("healthcare")
        if amenity in FACILITY_AMENITIES and len(coords) >= 3:
            key = f"way:{wid}"
            if key not in seen_facilities:
                seen_facilities.add(key)
                clon = sum(c[0] for c in coords) / len(coords)
                clat = sum(c[1] for c in coords) / len(coords)
                ftype = "hospital" if amenity in ("clinic", "doctors") else str(amenity)
                name = str(
                    tags.get("name") or tags.get("name:en") or f"{ftype.title()} #{wid}"
                )[:250]
                facilities_rows.append(
                    {
                        "type": ftype[:95],
                        "name": name,
                        "capacity": 250 if ftype == "hospital" else 150,
                        "service_radius_m": 3000.0
                        if ftype in ("hospital", "fire_station")
                        else 2000.0,
                        "lon": clon,
                        "lat": clat,
                        "source": f"OpenStreetMap:way/{wid}",
                    }
                )

        # 3. Buildings
        btag = tags.get("building")
        if btag and str(btag).lower() not in ("no", "none"):
            wkt = _polygon_wkt(coords)
            if wkt:
                btype = str(btag).strip().lower()[:95]
                explicit_floors = _parse_float(tags.get("building:levels"))
                explicit_height = _parse_float(tags.get("height"))
                base_floors = TYPICAL_FLOORS.get(btype, 3)
                floors = (
                    max(1, int(round(explicit_floors)))
                    if explicit_floors
                    else max(1, int(round(base_floors * _det_jitter(wid, 0.8, 1.25))))
                )
                height_m = round(
                    explicit_height if explicit_height else floors * FLOOR_HEIGHT_M, 2
                )
                area_m2 = _approx_poly_area_m2(coords)
                is_non_res = btype in (
                    "industrial",
                    "warehouse",
                    "factory",
                    "commercial",
                    "retail",
                    "office",
                    "school",
                    "college",
                    "university",
                    "hospital",
                    "garage",
                    "shed",
                    "roof",
                )
                pop_est = (
                    0
                    if is_non_res
                    else max(2, min(800, int(round((area_m2 * floors * 0.65) / 32.0))))
                )
                land_use = (
                    "commercial"
                    if btype in ("commercial", "retail", "office", "supermarket", "mall", "hotel")
                    else "industrial"
                    if btype in ("industrial", "warehouse", "factory")
                    else "institutional"
                    if btype in ("hospital", "school", "college", "university", "civic", "public")
                    else "residential"
                )
                buildings_rows.append(
                    {
                        "height_m": min(180.0, max(3.0, height_m)),
                        "floors": min(60, floors),
                        "building_type": btype,
                        "land_use": land_use,
                        "confidence": 0.95 if (explicit_floors or explicit_height) else 0.80,
                        "population_estimate": pop_est,
                        "risk_score": 0.15,
                        "wkt": wkt,
                        "source": "OpenStreetMap",
                    }
                )

        # 4. Water bodies
        if tags.get("natural") == "water" or tags.get("waterway") == "riverbank" or tags.get("water"):
            wkt = _polygon_wkt(coords)
            if wkt:
                wtype = str(tags.get("water") or tags.get("waterway") or "water")[:95]
                water_rows.append(
                    {
                        "type": wtype,
                        "seasonality": str(
                            "intermittent"
                            if tags.get("intermittent") == "yes"
                            else "perennial"
                        )[:48],
                        "wkt": wkt,
                        "source": "OpenStreetMap",
                    }
                )

        # 5. Land parcels (landuse polygons)
        lu = tags.get("landuse")
        if lu:
            wkt = _polygon_wkt(coords)
            if wkt:
                lu_str = str(lu).strip().lower()[:95]
                zoning_map = {
                    "residential": "residential",
                    "commercial": "commercial",
                    "retail": "commercial",
                    "industrial": "industrial",
                    "farmland": "agricultural",
                    "meadow": "green_belt",
                    "grass": "green_belt",
                    "forest": "eco_sensitive",
                }
                dev_status = (
                    "vacant"
                    if lu_str in ("farmland", "meadow", "grass", "brownfield", "greenfield", "construction")
                    else "developed"
                )
                parcel_rows.append(
                    {
                        "land_use": lu_str,
                        "zoning": zoning_map.get(lu_str, "mixed_use"),
                        "development_status": dev_status,
                        "slope_deg": 1.5,
                        "elevation_m": 12.0,
                        "flood_risk": 0.15,
                        "wkt": wkt,
                        "source": "OpenStreetMap",
                    }
                )

    return {
        "roads": roads_rows,
        "buildings": buildings_rows,
        "facilities": facilities_rows,
        "water_bodies": water_rows,
        "land_parcels": parcel_rows,
    }


def _chunked(seq: list[dict[str, Any]], size: int = 500):
    for idx in range(0, len(seq), size):
        yield seq[idx : idx + size]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Seed PostGIS with cached real OpenStreetMap layers for NagarX."
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse cached Overpass files and report counts without touching PostgreSQL.",
    )
    args = ap.parse_args()

    print("Parsing checked-in OpenStreetMap Overpass caches...")
    layers = collect_cached_osm()
    for name, rows in layers.items():
        print(f"  prepared {name:16s}: {len(rows):6d} features")

    if args.dry_run:
        print("\n[DRY RUN] No database writes performed.")
        return 0

    from sqlalchemy import text
    from app.storage.bootstrap import apply_schema
    from app.storage.db import check_connection, get_engine

    info = check_connection()
    if not info.get("connected"):
        print(f"\n[ERROR] Cannot connect to PostGIS: {info.get('error')}")
        print("        Make sure Docker PostGIS is running:")
        print("          cp -n .env.example .env")
        print("          docker compose up -d db")
        return 1

    if info.get("missing_tables"):
        print(
            f"Applying db/schema.sql (missing tables: {', '.join(info['missing_tables'])})..."
        )
        apply_schema()

    engine = get_engine()
    written: dict[str, int] = {}

    with engine.begin() as conn:
        conn.execute(
            text(f"TRUNCATE TABLE {', '.join(OWNED_TABLES)} RESTART IDENTITY CASCADE")
        )

        # 1. Roads
        road_sql = text(
            """
            INSERT INTO roads
                (road_class, lanes, width_m, speed_limit, capacity, surface, oneway, geometry, source)
            VALUES
                (:road_class, :lanes, :width_m, :speed_limit, :capacity, :surface, :oneway,
                 ST_Multi(ST_GeomFromText(:wkt, 4326)), :source)
            """
        )
        for batch in _chunked(layers["roads"], 500):
            conn.execute(road_sql, batch)
        written["roads"] = conn.execute(text("SELECT COUNT(*) FROM roads")).scalar_one()

        # 2. Facilities
        fac_sql = text(
            """
            INSERT INTO facilities
                (type, name, capacity, service_radius_m, geometry, source)
            VALUES
                (:type, :name, :capacity, :service_radius_m,
                 ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), :source)
            """
        )
        if layers["facilities"]:
            conn.execute(fac_sql, layers["facilities"])
        written["facilities"] = conn.execute(
            text("SELECT COUNT(*) FROM facilities")
        ).scalar_one()

        # 3. Water bodies
        water_sql = text(
            """
            INSERT INTO water_bodies (type, seasonality, geometry, source)
            SELECT
                CAST(:type AS varchar(100)),
                CAST(:seasonality AS varchar(50)),
                geom,
                CAST(:source AS varchar(255))
            FROM (
                SELECT ST_Multi(
                    ST_CollectionExtract(
                        ST_MakeValid(ST_GeomFromText(CAST(:wkt AS text), 4326)),
                        3
                    )
                ) AS geom
            ) q
            WHERE geom IS NOT NULL AND NOT ST_IsEmpty(geom)
            """
        )
        if layers["water_bodies"]:
            conn.execute(water_sql, layers["water_bodies"])
        written["water_bodies"] = conn.execute(
            text("SELECT COUNT(*) FROM water_bodies")
        ).scalar_one()

        # 4. Buildings
        bldg_sql = text(
            """
            INSERT INTO buildings
                (height_m, floors, building_type, land_use, confidence,
                 population_estimate, risk_score, geometry, source)
            SELECT
                CAST(:height_m AS numeric(5,2)),
                CAST(:floors AS integer),
                CAST(:building_type AS varchar(100)),
                CAST(:land_use AS varchar(100)),
                CAST(:confidence AS numeric(3,2)),
                CAST(:population_estimate AS integer),
                CAST(:risk_score AS numeric(3,2)),
                geom,
                CAST(:source AS varchar(255))
            FROM (
                SELECT ST_Multi(
                    ST_CollectionExtract(
                        ST_MakeValid(ST_GeomFromText(CAST(:wkt AS text), 4326)),
                        3
                    )
                ) AS geom
            ) q
            WHERE geom IS NOT NULL AND NOT ST_IsEmpty(geom)
            """
        )
        for batch in _chunked(layers["buildings"], 500):
            conn.execute(bldg_sql, batch)
        written["buildings"] = conn.execute(
            text("SELECT COUNT(*) FROM buildings")
        ).scalar_one()

        # 5. Land parcels (single POLYGON required by schema)
        parcel_sql = text(
            """
            INSERT INTO land_parcels
                (land_use, zoning, development_status, slope_deg, elevation_m,
                 flood_risk, geometry, source)
            SELECT
                CAST(:land_use AS varchar(100)),
                CAST(:zoning AS varchar(100)),
                CAST(:development_status AS varchar(100)),
                CAST(:slope_deg AS numeric(4,2)),
                CAST(:elevation_m AS numeric(6,2)),
                CAST(:flood_risk AS numeric(3,2)),
                geom,
                CAST(:source AS varchar(255))
            FROM (
                SELECT ST_GeometryN(
                    ST_CollectionExtract(
                        ST_MakeValid(ST_GeomFromText(CAST(:wkt AS text), 4326)),
                        3
                    ),
                    1
                ) AS geom
            ) q
            WHERE geom IS NOT NULL
              AND NOT ST_IsEmpty(geom)
              AND GeometryType(geom) = 'POLYGON'
            """
        )
        if layers["land_parcels"]:
            conn.execute(parcel_sql, layers["land_parcels"])

        # Update parcel flood_risk based on real PostGIS distance to water_bodies
        conn.execute(
            text(
                """
                UPDATE land_parcels p
                SET flood_risk = CASE
                    WHEN EXISTS (
                        SELECT 1 FROM water_bodies w
                        WHERE ST_DWithin(p.geometry::geography, w.geometry::geography, 80.0)
                    ) THEN 0.75
                    WHEN EXISTS (
                        SELECT 1 FROM water_bodies w
                        WHERE ST_DWithin(p.geometry::geography, w.geometry::geography, 250.0)
                    ) THEN 0.40
                    ELSE 0.10
                END
                """
            )
        )
        written["land_parcels"] = conn.execute(
            text("SELECT COUNT(*) FROM land_parcels")
        ).scalar_one()

        # 6. Population zones derived from ingested buildings
        conn.execute(
            text(
                """
                INSERT INTO population_zones
                    (population, households, density_per_sqkm, geometry, source)
                SELECT
                    SUM(b.population_estimate)::int,
                    GREATEST(1, (SUM(b.population_estimate) / 4.5)::int),
                    LEAST(
                        99999999.99,
                        COALESCE(
                            SUM(b.population_estimate) /
                            NULLIF(ST_Area(g.cell::geography) / 1000000.0, 0),
                            0
                        )
                    )::numeric(10,2),
                    g.cell,
                    'derived:buildings'
                FROM (
                    SELECT ST_SetSRID(
                        (ST_SquareGrid(0.005, ST_Extent(geometry)::geometry)).geom,
                        4326
                    ) AS cell
                    FROM buildings
                ) g
                JOIN buildings b ON ST_Intersects(b.geometry, g.cell)
                GROUP BY g.cell
                HAVING SUM(b.population_estimate) > 0
                """
            )
        )
        written["population_zones"] = conn.execute(
            text("SELECT COUNT(*) FROM population_zones")
        ).scalar_one()

        # 7. Dataset provenance & baseline scenario
        conn.execute(
            text(
                """
                INSERT INTO dataset_metadata
                    (dataset_name, source, license, download_date, resolution, crs, confidence)
                VALUES
                    ('OpenStreetMap Pilot Corridor (Cached Overpass)',
                     'OpenStreetMap Contributors', 'ODbL 1.0', :d,
                     'Vector topology', 'EPSG:4326', 'High')
                """
            ),
            {"d": date.today()},
        )
        scen_count = conn.execute(text("SELECT COUNT(*) FROM scenarios")).scalar_one()
        if scen_count == 0:
            conn.execute(
                text(
                    """
                    INSERT INTO scenarios (name, description, base_version, created_by)
                    VALUES (
                        'New Panvel — Kalundre Baseline',
                        'Baseline spatial twin state seeded from OpenStreetMap vector layers.',
                        'v1.0',
                        'system_seed'
                    )
                    """
                )
            )

    print("\n" + "=" * 60)
    print("  NAGAR-X POSTGIS SEED COMPLETE")
    print("=" * 60)
    for k, v in written.items():
        print(f"  {k:20s}: {v:8d} rows")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
