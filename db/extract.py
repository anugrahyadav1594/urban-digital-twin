"""Populate the comparison-region tables from OpenStreetMap.

Why this exists alongside db/extract_batch.py:

  * extract_batch.py needs geopandas, which is a heavy dependency (GDAL/GEOS
    wheels) that is not installed in this project's venv.
  * It also imports db/db_config.py, which reads POSTGIS_* with os.getenv and
    loads no .env file at all - so it silently connects to port 5432 with the
    default password even when the real database is elsewhere.

This script avoids both problems. It reuses the BACKEND's own Settings object,
which already walks up to the repo-root .env and is demonstrably connecting
(the API answers), so the credentials are guaranteed to match. Geometry is
written as WKT through plain SQL, so only shapely + sqlalchemy + requests are
needed - all already installed.

Usage, from the repo root:

    source .venv/bin/activate
    python db/extract_regions.py                 # all regions that are missing
    python db/extract_regions.py jnpt_port       # just one
    python db/extract_regions.py --force         # re-extract even if present
    python db/extract_regions.py --dry-run       # query OSM, write nothing
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Iterable

# Import the backend's settings rather than db/db_config.py.
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

try:
    import requests
except ImportError:
    sys.exit("requests is not installed:  pip install requests")

try:
    from shapely.geometry import LineString, Point, Polygon
    from shapely.ops import unary_union            # noqa: F401  (kept for parity)
except ImportError:
    sys.exit("shapely is not installed:  pip install shapely")

try:
    from sqlalchemy import create_engine, text
except ImportError:
    sys.exit("sqlalchemy is not installed:  pip install sqlalchemy")

try:
    from app.core.config import get_settings
except Exception as exc:                                   # noqa: BLE001
    sys.exit(
        "Could not import the backend settings (%s).\n"
        "Run this from the repo root with the venv active." % exc
    )

# Same four areas as db/utils.py REGIONAL_BOUNDS, as (W, S, E, N).
REGIONS: dict[str, tuple[float, float, float, float]] = {
    "adivali_devad": (73.1300, 18.9900, 73.1500, 19.0050),
    "jnpt_port":     (72.9300, 18.9300, 73.0000, 18.9800),
    "chandigarh":    (76.7650, 30.7300, 76.7900, 30.7500),
    "rotterdam":     (4.4500, 51.8900, 4.5000, 51.9200),
}

MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

# layer -> Overpass selector. Order matters only for readability.
#
# The first four layers are geometry only and were enough for map display.
# `facilities` and `landuse` were added so the comparison cities can actually
# be SCORED: without amenity points and land-use polygons, eight of the ten
# scoring dimensions have no input and return null.
QUERIES: dict[str, str] = {
    "roads":     'way["highway"]',
    "buildings": 'way["building"]',
    "water":     'way["natural"="water"];way["waterway"];way["landuse"="reservoir"]',
    "bridges":   'way["bridge"]["bridge"!="no"]',
    # Amenities are tagged on nodes AND ways (a hospital is often a building
    # polygon), so both are collected and reduced to a representative point.
    "facilities": (
        'node["amenity"];way["amenity"];'
        'node["healthcare"];way["healthcare"];'
        'node["leisure"];way["leisure"];'
        'node["shop"="chemist"]'
    ),
    "landuse":   'way["landuse"];way["natural"="wood"];way["leisure"="park"];'
                 'way["leisure"="garden"];way["leisure"="pitch"]',
}

# PostGIS geometry type per layer. Facilities are reduced to points so they
# map cleanly onto the Facility record the scoring engine expects.
GEOM_TYPE: dict[str, str] = {
    "roads":      "MULTILINESTRING",
    "bridges":    "MULTILINESTRING",
    "buildings":  "MULTIPOLYGON",
    "water":      "MULTIPOLYGON",
    "landuse":    "MULTIPOLYGON",
    "facilities": "POINT",
}

# Overpass output mode. `out center` gives ways a representative point, which
# is what the facilities layer needs; `out geom` gives full coordinate lists.
OUT_MODE: dict[str, str] = {"facilities": "out center"}


def overpass(selector: str, bbox: tuple[float, float, float, float],
             timeout: int = 180, out_mode: str = "out geom") -> list[dict[str, Any]]:
    """Run one Overpass query, trying each mirror in turn."""
    w, s, e, n = bbox
    parts = "".join(f"{sel}({s},{w},{n},{e});" for sel in selector.split(";") if sel)
    ql = f"[out:json][timeout:{timeout}];({parts});{out_mode};"
    last = ""
    for ep in MIRRORS:
        try:
            r = requests.post(ep, data={"data": ql}, timeout=timeout + 30)
            if r.status_code == 200:
                return r.json().get("elements", [])
            last = f"HTTP {r.status_code} from {ep}"
            # 429/504 mean "busy", so give the next mirror a moment.
            time.sleep(2)
        except Exception as exc:                            # noqa: BLE001
            last = f"{type(exc).__name__} from {ep}"
            continue
    print(f"      all mirrors failed ({last})")
    return []


def to_geometry(el: dict[str, Any], want_polygon: bool):
    """Build a shapely geometry from an Overpass 'out geom' way."""
    geom = el.get("geometry") or []
    pts = [(p["lon"], p["lat"]) for p in geom
           if p.get("lon") is not None and p.get("lat") is not None]
    if len(pts) < 2:
        return None
    try:
        if want_polygon and len(pts) >= 4 and pts[0] == pts[-1]:
            g = Polygon(pts)
            # A self-intersecting ring is invalid; buffer(0) repairs it.
            # Never apply this to lines - it erases them.
            if not g.is_valid:
                g = g.buffer(0)
            return g if (not g.is_empty and g.is_valid) else None
        if want_polygon:
            return None                     # unclosed way is not a building
        g = LineString(pts)
        return g if not g.is_empty else None
    except Exception:                                       # noqa: BLE001
        return None


def to_point(el: dict[str, Any]):
    """Representative point for an amenity, whether node or way.

    Overpass `out center` puts a way's centroid in el['center']; nodes carry
    lat/lon directly. Either way the scoring engine wants a single point.
    """
    if el.get("lat") is not None and el.get("lon") is not None:
        return Point(float(el["lon"]), float(el["lat"]))
    c = el.get("center") or {}
    if c.get("lat") is not None and c.get("lon") is not None:
        return Point(float(c["lon"]), float(c["lat"]))
    # Fall back to the centroid of an explicit geometry list.
    geom = el.get("geometry") or []
    pts = [(p["lon"], p["lat"]) for p in geom
           if p.get("lon") is not None and p.get("lat") is not None]
    if not pts:
        return None
    if len(pts) == 1:
        return Point(pts[0])
    try:
        ring = Polygon(pts) if (len(pts) >= 4 and pts[0] == pts[-1]) else LineString(pts)
        c2 = ring.centroid
        return c2 if not c2.is_empty else None
    except Exception:                                       # noqa: BLE001
        return None


def create_table(conn, table: str, gtype: str) -> None:
    conn.execute(text(f'DROP TABLE IF EXISTS public."{table}"'))
    conn.execute(text(f'''
        CREATE TABLE public."{table}" (
            id        bigserial PRIMARY KEY,
            osm_id    bigint,
            name      text,
            kind      text,
            category  text,
            geometry  geometry({gtype}, 4326)
        )
    '''))
    conn.execute(text(
        f'CREATE INDEX "{table}_geom_idx" ON public."{table}" USING GIST (geometry)'))


# OSM tag value -> the category word the scoring engine matches on.
# city_score.py tests with substring matching against these tuples:
#   HEALTH, EDUCATION, RECREATION, EMERGENCY, GREEN_USES.
# Mapping here (rather than in the engine) keeps OSM vocabulary out of the
# scoring logic.
FACILITY_CATEGORY: dict[str, str] = {
    # health
    "hospital": "hospital", "clinic": "clinic", "doctors": "doctor",
    "pharmacy": "pharmacy", "dentist": "clinic", "healthcare": "health",
    "nursing_home": "health", "social_facility": "health",
    # education
    "school": "school", "college": "college", "university": "university",
    "kindergarten": "kindergarten", "library": "library",
    # emergency
    "fire_station": "fire_station", "police": "police",
    "ambulance_station": "ambulance",
    # recreation / culture
    "park": "park", "garden": "garden", "playground": "playground",
    "sports_centre": "sport", "fitness_centre": "gym", "pitch": "sport",
    "swimming_pool": "swimming", "stadium": "stadium", "theatre": "theatre",
    "community_centre": "community", "arts_centre": "cultural",
    "sports_hall": "sport", "recreation_ground": "recreation",
}

# landuse/natural/leisure tag -> parcel land_use value. GREEN_USES in the
# scoring engine looks for park/green/forest/recreation/garden/open_space.
LANDUSE_CATEGORY: dict[str, str] = {
    "residential": "residential", "commercial": "commercial",
    "retail": "commercial", "industrial": "industrial",
    "farmland": "agriculture", "farmyard": "agriculture",
    "orchard": "agriculture", "meadow": "green",
    "grass": "green", "greenfield": "green", "village_green": "green",
    "forest": "forest", "wood": "forest", "recreation_ground": "recreation",
    "park": "park", "garden": "garden", "pitch": "recreation",
    "cemetery": "open_space", "allotments": "green",
    "construction": "vacant", "brownfield": "vacant",
    "quarry": "industrial", "railway": "infrastructure",
    "port": "industrial", "harbour": "industrial", "military": "restricted",
    "institutional": "institutional", "education": "institutional",
    "religious": "institutional",
}


def classify_facility(tags: dict[str, Any]) -> tuple[str, str] | None:
    """Return (kind, category) for an amenity element, or None to skip it."""
    for key in ("amenity", "healthcare", "leisure", "shop"):
        val = tags.get(key)
        if not val:
            continue
        val = str(val).lower()
        cat = FACILITY_CATEGORY.get(val)
        if cat:
            return val, cat
        # healthcare=* is a health facility even when the value is unusual.
        if key == "healthcare":
            return val, "health"
        if key == "shop" and val == "chemist":
            return val, "pharmacy"
    return None


def classify_landuse(tags: dict[str, Any]) -> tuple[str, str] | None:
    for key in ("landuse", "leisure", "natural"):
        val = tags.get(key)
        if not val:
            continue
        val = str(val).lower()
        cat = LANDUSE_CATEGORY.get(val)
        if cat:
            return val, cat
    return None


def extract_layer(conn, region: str, layer: str,
                  bbox: tuple[float, float, float, float],
                  dry_run: bool) -> int:
    gtype = GEOM_TYPE[layer]
    is_point = gtype == "POINT"
    polygon = gtype == "MULTIPOLYGON"
    table = f"{region}_{layer}"
    print(f"    {layer:<10} querying OSM…", flush=True)

    elements = overpass(QUERIES[layer], bbox,
                        out_mode=OUT_MODE.get(layer, "out geom"))
    if not elements:
        print(f"    {layer:<10} 0 elements returned")
        return 0

    rows: list[dict[str, Any]] = []
    seen: set[Any] = set()
    for el in elements:
        tags = el.get("tags") or {}

        if layer == "facilities":
            hit = classify_facility(tags)
            if hit is None:
                continue                     # untagged / irrelevant amenity
            kind, category = hit
            g = to_point(el)
        elif layer == "landuse":
            hit = classify_landuse(tags)
            if hit is None:
                continue
            kind, category = hit
            g = to_geometry(el, True)
        else:
            g = to_geometry(el, polygon)
            kind = (tags.get("highway") or tags.get("building")
                    or tags.get("waterway") or tags.get("natural") or "")
            category = ""

        if g is None or g.is_empty:
            continue

        # A hospital mapped as both a node and a building way would otherwise
        # be counted twice, inflating per-capita facility scores.
        key = (el.get("id"), el.get("type"))
        if key in seen:
            continue
        seen.add(key)

        rows.append({
            "osm_id": el.get("id"),
            "name": (tags.get("name") or "")[:200],
            "kind": str(kind)[:80],
            "category": str(category)[:80],
            "wkt": g.wkt,
        })

    if not rows:
        print(f"    {layer:<10} {len(elements)} elements, 0 usable geometries")
        return 0

    if dry_run:
        print(f"    {layer:<10} {len(rows)} features (dry run, nothing written)")
        return len(rows)

    create_table(conn, table, gtype)
    # Points go in as-is; lines and polygons are normalised to MULTI*.
    geom_sql = ("ST_SetSRID(ST_GeomFromText(:wkt), 4326)" if is_point
                else "ST_Multi(ST_SetSRID(ST_GeomFromText(:wkt), 4326))")
    ins = text(f'''
        INSERT INTO public."{table}" (osm_id, name, kind, category, geometry)
        VALUES (:osm_id, :name, :kind, :category, {geom_sql})
    ''')
    # Chunked so a huge region does not build one enormous statement.
    for i in range(0, len(rows), 500):
        conn.execute(ins, rows[i:i + 500])
    print(f"    {layer:<10} {len(rows)} features -> {table}")
    return len(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("regions", nargs="*", help="region ids (default: all missing)")
    ap.add_argument("--force", action="store_true",
                    help="re-extract even if the tables already hold rows")
    ap.add_argument("--dry-run", action="store_true",
                    help="query OSM but write nothing")
    args = ap.parse_args()

    settings = get_settings()
    url = settings.database_url
    shown = url.replace(settings.postgis_password, "***")
    print(f"database: {shown}")

    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception as exc:                                # noqa: BLE001
        print(f"\nCannot connect: {exc}")
        print("These are the same credentials the backend uses, so if the API"
              " is working, check that this shell has the repo-root .env.")
        return 1

    targets: Iterable[str] = args.regions or list(REGIONS)
    bad = [r for r in targets if r not in REGIONS]
    if bad:
        print(f"unknown region(s): {bad}; valid: {list(REGIONS)}")
        return 2

    total = 0
    for region in targets:
        bbox = REGIONS[region]
        print(f"\n=== {region} ===  bbox {bbox}")

        if not args.force and not args.dry_run:
            with engine.connect() as c:
                have = 0
                for layer in QUERIES:
                    t = f"{region}_{layer}"
                    exists = c.execute(text("SELECT to_regclass(:t)"),
                                       {"t": f"public.{t}"}).scalar()
                    if exists:
                        have += c.execute(
                            text(f'SELECT count(*) FROM public."{t}"')).scalar() or 0
            if have:
                print(f"  already has {have} features - skipping (use --force)")
                continue

        # One transaction per region: a mirror failure mid-region rolls back
        # rather than leaving half a city behind.
        with engine.begin() as conn:
            n = 0
            for layer in QUERIES:
                try:
                    n += extract_layer(conn, region, layer, bbox, args.dry_run)
                except Exception as exc:                    # noqa: BLE001
                    print(f"    {layer:<10} FAILED: {type(exc).__name__}: {exc}")
            print(f"  {region}: {n} features")
            total += n

    print(f"\ntotal: {total} features")
    if total and not args.dry_run:
        print("\nRestart uvicorn, then re-run:  bash verify_regions.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())