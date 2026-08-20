"""Read comparison-region tables as engine domain records.

`SpatialRepository` reads the canonical pilot tables (roads, land_parcels,
facilities, population_zones) through the ORM. The three comparison cities
do not live there: `db/extract.py` writes them to `{region}_{layer}` tables
with a flat OSM-derived schema and no demographics.

This repository closes that gap so `score_city()` can run over any of the
four regions with the same inputs. Three things need care:

1.  CRS. The scoring engine does metric maths and assumes a projected CRS.
    The configured `analysis_srid` (32643) is correct for the three Indian
    areas but wrong for Rotterdam, which is UTM zone 31N. Forcing Rotterdam
    through 32643 inflates distances by roughly 23%, silently corrupting
    every per-km2 and per-metre dimension. The UTM zone is therefore
    resolved per region from its own centroid.

2.  Population. OSM has none. It is estimated from residential building
    footprints (see `estimate_population`), and every payload that uses it
    is labelled so the number is never mistaken for a census count.

3.  Flood risk. Also absent from OSM. A distance-to-water proxy is applied
    so the `constraints` dimension has an input; it is likewise labelled.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..engines.contracts import Facility, Parcel, PopulationZone, Road
from ..engines.crs import to_analysis, utm_srid_for

# Layers written by db/extract.py.
GEOMETRY_LAYERS = ("roads", "buildings", "water", "bridges")
SCORING_LAYERS = ("facilities", "landuse")

# Study-area bounds (W, S, E, N). Mirrors db/utils.py REGIONAL_BOUNDS and the
# regions router. Defined here so services can resolve a region without
# importing from the API layer, which would invert the dependency direction.
REGIONAL_BOUNDS: dict[str, tuple[float, float, float, float]] = {
    "adivali_devad": (73.1300, 18.9900, 73.1500, 19.0050),
    "jnpt_port":     (72.9300, 18.9300, 73.0000, 18.9800),
    "chandigarh":    (76.7650, 30.7300, 76.7900, 30.7500),
    "rotterdam":     (4.4500, 51.8900, 4.5000, 51.9200),
}

# --- population estimation constants -------------------------------------
# Documented here rather than buried in code because they are assumptions,
# not measurements, and reviewers must be able to challenge them.
DEFAULT_FLOORS = 2.0          # storeys, when building:levels is absent
FLOOR_AREA_PER_PERSON = 30.0  # m2 of residential floor space per person
RESIDENTIAL_FRACTION = 0.75   # share of an untagged building assumed housing

# Building tag values that are definitely NOT housing.
NON_RESIDENTIAL = {
    "industrial", "warehouse", "retail", "commercial", "office", "shop",
    "school", "hospital", "church", "mosque", "temple", "garage", "garages",
    "hangar", "shed", "roof", "carport", "farm_auxiliary", "barn", "stable",
    "service", "transportation", "train_station", "civic", "public",
    "government", "hotel", "supermarket", "kiosk", "storage_tank", "silo",
}
# Values that are definitely housing.
RESIDENTIAL = {
    "residential", "house", "apartments", "detached", "semidetached_house",
    "terrace", "bungalow", "dormitory", "hut", "cabin", "farm",
}

# Distance from open water within which a parcel is treated as flood-exposed.
FLOOD_BUFFER_M = 150.0


def analysis_srid_for(bbox: tuple[float, float, float, float]) -> int:
    """Projected CRS appropriate to this bbox, from its centroid."""
    minx, miny, maxx, maxy = bbox
    return utm_srid_for((minx + maxx) / 2.0, (miny + maxy) / 2.0)


class RegionRepository:
    """Loads one comparison region's extracted tables as domain records."""

    def __init__(self, session: Session, region: str,
                 bbox: tuple[float, float, float, float]):
        self.s = session
        self.region = region
        self.bbox = bbox
        self.srid = analysis_srid_for(bbox)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _table(self, layer: str) -> str:
        return f"{self.region}_{layer}"

    def has(self, layer: str) -> bool:
        return bool(self.s.execute(
            text("SELECT to_regclass(:t)"),
            {"t": f"public.{self._table(layer)}"}).scalar())

    def _has_column(self, layer: str, column: str) -> bool:
        """Older extractions predate the `category` column."""
        return bool(self.s.execute(text("""
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :t
              AND column_name = :c
        """), {"t": self._table(layer), "c": column}).scalar())

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for layer in GEOMETRY_LAYERS + SCORING_LAYERS:
            if not self.has(layer):
                continue
            n = self.s.execute(
                text(f'SELECT count(*) FROM public."{self._table(layer)}"')).scalar()
            if n:
                out[layer] = int(n)
        return out

    def _shapes(self, layer: str, extra_cols: str = "") -> list[dict[str, Any]]:
        """Rows as dicts with a shapely geometry already in the analysis CRS."""
        if not self.has(layer):
            return []
        from shapely import wkb

        cols = f", {extra_cols}" if extra_cols else ""
        rows = self.s.execute(text(
            f'SELECT id, name, kind{cols}, ST_AsBinary(geometry) AS g '
            f'FROM public."{self._table(layer)}"'
        )).mappings().all()

        out: list[dict[str, Any]] = []
        for r in rows:
            raw = r.get("g")
            if raw is None:
                continue
            try:
                geom = wkb.loads(bytes(raw))
            except Exception:                                # noqa: BLE001
                continue
            if geom.is_empty:
                continue
            try:
                geom = to_analysis(geom, self.srid)
            except Exception:                                # noqa: BLE001
                continue
            d = dict(r)
            d["geometry"] = geom
            d.pop("g", None)
            out.append(d)
        return out

    # ------------------------------------------------------------------
    # domain records
    # ------------------------------------------------------------------
    def roads(self) -> list[Road]:
        out: list[Road] = []
        for r in self._shapes("roads"):
            geom = r["geometry"]
            # MULTILINESTRING -> the engine wants a single LineString.
            if geom.geom_type == "MultiLineString":
                parts = [g for g in geom.geoms if not g.is_empty]
                if not parts:
                    continue
                geom = max(parts, key=lambda g: g.length)
            elif geom.geom_type != "LineString":
                continue
            out.append(Road(
                id=f"{self.region}_road_{r['id']}",
                geometry=geom,
                road_class=str(r.get("kind") or "local"),
            ))
        return out

    def facilities(self) -> list[Facility]:
        """Amenity points, typed with the category the scoring engine matches."""
        if not self.has("facilities"):
            return []
        has_cat = self._has_column("facilities", "category")
        rows = self._shapes("facilities", "category" if has_cat else "")
        out: list[Facility] = []
        for r in rows:
            geom = r["geometry"]
            if geom.geom_type != "Point":
                geom = geom.centroid
            # Prefer the mapped category; fall back to the raw OSM tag so an
            # older extraction without the column still scores something.
            ftype = str(r.get("category") or r.get("kind") or "generic")
            out.append(Facility(
                id=f"{self.region}_fac_{r['id']}",
                geometry=geom,
                type=ftype,
            ))
        return out

    def parcels(self) -> list[Parcel]:
        """Land-use polygons as parcels, with a water-distance flood proxy."""
        if not self.has("landuse"):
            return []
        has_cat = self._has_column("landuse", "category")
        rows = self._shapes("landuse", "category" if has_cat else "")
        if not rows:
            return []

        water = [w["geometry"] for w in self._shapes("water")]
        tree = None
        if water:
            try:
                from shapely.strtree import STRtree
                tree = STRtree(water)
            except Exception:                                # noqa: BLE001
                tree = None

        out: list[Parcel] = []
        for r in rows:
            geom = r["geometry"]
            if geom.geom_type not in ("Polygon", "MultiPolygon"):
                continue
            land_use = str(r.get("category") or r.get("kind") or "")

            # Flood proxy: a parcel within FLOOD_BUFFER_M of mapped water is
            # treated as exposed. This is a proxy, not a hydrological model,
            # and the API labels it as such.
            flood = 0.0
            if tree is not None:
                try:
                    if len(tree.query(geom.buffer(FLOOD_BUFFER_M))) > 0:
                        flood = 0.6
                except Exception:                            # noqa: BLE001
                    flood = 0.0

            out.append(Parcel(
                id=f"{self.region}_parcel_{r['id']}",
                geometry=geom,
                area=float(geom.area or 0.0),
                land_use=land_use,
                flood_risk=flood,
            ))
        return out

    # ------------------------------------------------------------------
    # population
    # ------------------------------------------------------------------
    def estimate_population(self) -> tuple[list[PopulationZone], dict[str, Any]]:
        """Estimate residents from residential building footprints.

        population = footprint m2 x floors x residential share / m2 per person

        Returns the zones plus the evidence behind the number, so the API can
        show exactly how it was derived instead of asserting a bare total.
        """
        buildings = self._shapes("buildings")
        if not buildings:
            return [], {"method": "none", "reason": "no buildings extracted"}

        total_pop = 0.0
        residential_area = 0.0
        counted = 0
        zones: list[PopulationZone] = []

        for b in buildings:
            geom = b["geometry"]
            area = float(geom.area or 0.0)
            if area <= 0:
                continue
            kind = str(b.get("kind") or "").lower()
            if kind in NON_RESIDENTIAL:
                continue
            if kind in RESIDENTIAL:
                share = 1.0
            elif kind in ("yes", ""):
                # Untagged building: assume a share of it is housing.
                share = RESIDENTIAL_FRACTION
            else:
                share = RESIDENTIAL_FRACTION

            floor_area = area * DEFAULT_FLOORS * share
            pop = floor_area / FLOOR_AREA_PER_PERSON
            if pop <= 0:
                continue
            total_pop += pop
            residential_area += area
            counted += 1
            zones.append(PopulationZone(
                id=f"{self.region}_pz_{b['id']}",
                geometry=geom.centroid,
                population=pop,
            ))

        evidence = {
            "method": "building-footprint estimate",
            "buildingsTotal": len(buildings),
            "buildingsResidential": counted,
            "residentialFootprintM2": round(residential_area),
            "assumedFloors": DEFAULT_FLOORS,
            "m2PerPerson": FLOOR_AREA_PER_PERSON,
            "residentialFraction": RESIDENTIAL_FRACTION,
            "estimatedPopulation": round(total_pop),
        }
        return zones, evidence

    # ------------------------------------------------------------------
    def load(self) -> dict[str, Any]:
        """Everything score_city() needs, plus provenance detail."""
        zones, pop_evidence = self.estimate_population()
        return {
            "roads": self.roads(),
            "parcels": self.parcels(),
            "facilities": self.facilities(),
            "population_zones": zones,
            "population_evidence": pop_evidence,
            "analysis_srid": self.srid,
            "counts": self.counts(),
        }