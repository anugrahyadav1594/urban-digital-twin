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
    from shapely.geometry import LineString, Polygon
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
QUERIES: dict[str, str] = {
    "roads":     'way["highway"]',
    "buildings": 'way["building"]',
    "water":     'way["natural"="water"];way["waterway"];way["landuse"="reservoir"]',
    "bridges":   'way["bridge"]["bridge"!="no"]',
}


def overpass(selector: str, bbox: tuple[float, float, float, float],
             timeout: int = 180) -> list[dict[str, Any]]:
    """Run one Overpass query, trying each mirror in turn."""
    w, s, e, n = bbox
    parts = "".join(f"{sel}({s},{w},{n},{e});" for sel in selector.split(";") if sel)
    ql = f"[out:json][timeout:{timeout}];({parts});out geom;"
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


def create_table(conn, table: str, polygon: bool) -> None:
    gtype = "MULTIPOLYGON" if polygon else "MULTILINESTRING"
    conn.execute(text(f'DROP TABLE IF EXISTS public."{table}"'))
    conn.execute(text(f'''
        CREATE TABLE public."{table}" (
            id        bigserial PRIMARY KEY,
            osm_id    bigint,
            name      text,
            kind      text,
            geometry  geometry({gtype}, 4326)
        )
    '''))
    conn.execute(text(
        f'CREATE INDEX "{table}_geom_idx" ON public."{table}" USING GIST (geometry)'))


def extract_layer(conn, region: str, layer: str,
                  bbox: tuple[float, float, float, float],
                  dry_run: bool) -> int:
    polygon = layer == "buildings" or layer == "water"
    table = f"{region}_{layer}"
    print(f"    {layer:<10} querying OSM…", flush=True)

    elements = overpass(QUERIES[layer], bbox)
    if not elements:
        print(f"    {layer:<10} 0 elements returned")
        return 0

    rows: list[dict[str, Any]] = []
    for el in elements:
        g = to_geometry(el, polygon)
        if g is None:
            continue
        tags = el.get("tags") or {}
        kind = (tags.get("highway") or tags.get("building")
                or tags.get("waterway") or tags.get("natural") or "")
        rows.append({
            "osm_id": el.get("id"),
            "name": (tags.get("name") or "")[:200],
            "kind": str(kind)[:80],
            # ST_Multi normalises to the MULTI* column type.
            "wkt": g.wkt,
        })

    if not rows:
        print(f"    {layer:<10} {len(elements)} elements, 0 usable geometries")
        return 0

    if dry_run:
        print(f"    {layer:<10} {len(rows)} features (dry run, nothing written)")
        return len(rows)

    create_table(conn, table, polygon)
    ins = text(f'''
        INSERT INTO public."{table}" (osm_id, name, kind, geometry)
        VALUES (:osm_id, :name, :kind,
                ST_Multi(ST_SetSRID(ST_GeomFromText(:wkt), 4326)))
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