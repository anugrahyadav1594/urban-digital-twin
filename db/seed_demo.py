"""Seed the pilot sector with a small, realistic dataset for testing.

Adivali-devad / Chikhale (NAINA region, Navi Mumbai). Idempotent: truncates
the tables it fills before inserting.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import numpy as np
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Point, box
from geoalchemy2.shape import from_shape
from sqlalchemy import text

from app.models import (
    Building, Facility, LandParcel, PlanningConstraint, PopulationZone, Road,
    WaterBody, AdministrativeArea,
)
from app.storage.db import session_scope

MINX, MINY, MAXX, MAXY = 73.1300, 18.9900, 73.1500, 19.0050


def wkb(geom):
    return from_shape(geom, srid=4326)


def seed() -> dict[str, int]:
    with session_scope() as s:
        s.execute(text(
            "TRUNCATE TABLE planning_constraints, water_bodies, land_parcels, "
            "population_zones, facilities, buildings, roads, "
            "administrative_areas RESTART IDENTITY CASCADE;"
        ))

        # --- roads: 5x5 lattice across the sector ---
        xs = np.linspace(MINX, MAXX, 5)
        ys = np.linspace(MINY, MAXY, 5)
        for i, y in enumerate(ys):
            s.add(Road(road_class="secondary" if i % 2 else "primary",
                       lanes=2, width_m=7.0, speed_limit=40 if i % 2 else 50,
                       capacity=1000, oneway=False,
                       geometry=wkb(MultiLineString([LineString([(MINX, y), (MAXX, y)])])),
                       source="seed"))
        for j, x in enumerate(xs):
            s.add(Road(road_class="secondary" if j % 2 else "primary",
                       lanes=2, width_m=7.0, speed_limit=40 if j % 2 else 50,
                       capacity=1000, oneway=False,
                       geometry=wkb(MultiLineString([LineString([(x, MINY), (x, MAXY)])])),
                       source="seed"))

        # --- land parcels: inside each lattice block ---
        for i in range(4):
            for j in range(4):
                x0, x1 = xs[i] + 0.0008, xs[i + 1] - 0.0008
                y0, y1 = ys[j] + 0.0006, ys[j + 1] - 0.0006
                n = i * 4 + j
                s.add(LandParcel(
                    land_use=["residential", "mixed_use", "public_civic", "commercial"][n % 4],
                    zoning=["R-1 Low Density", "C-1 Commercial", "Public Utility", "R-2 High Density"][n % 4],
                    development_status="candidate",
                    slope_deg=round(0.5 + (n % 5) * 1.2, 2),
                    elevation_m=round(12.0 + n * 0.7, 2),
                    flood_risk=round(0.02 + (0.30 if i == 3 and j == 3 else 0.03 * (n % 4)), 2),
                    geometry=wkb(box(x0, y0, x1, y1)), source="seed"))

        # --- population zones: 4 quadrants ---
        mx, my = (MINX + MAXX) / 2, (MINY + MAXY) / 2
        for k, (bx, pop) in enumerate([
            (box(MINX, my, mx, MAXY), 24500), (box(mx, my, MAXX, MAXY), 31000),
            (box(MINX, MINY, mx, my), 18200), (box(mx, MINY, MAXX, my), 29800),
        ]):
            s.add(PopulationZone(population=pop, households=int(pop / 4.2),
                                 density_per_sqkm=round(pop / 1.5, 2),
                                 geometry=wkb(bx), source="seed-census"))
            s.add(AdministrativeArea(
                name=f"Ward {k+1}", type="administrative_ward", population=pop,
                geometry=wkb(MultiPolygon([bx])), source="seed"))

        # --- existing facilities ---
        for t, nm, cap, pt in [
            ("clinic", "Adivali Primary Healthcare Center", 50, Point(73.1340, 18.9950)),
            ("school", "Devad Sector Secondary School", 300, Point(73.1420, 19.0010)),
            ("hospital", "Panvel Rural Sub-District Hospital", 150, Point(73.1480, 18.9920)),
            ("fire_station", "Chikhale Emergency Response Post", 30, Point(73.1380, 19.0030)),
        ]:
            s.add(Facility(type=t, name=nm, capacity=cap,
                           service_radius_m=2000.0, geometry=wkb(pt), source="seed"))

        # --- buildings ---
        for i, x in enumerate(np.linspace(MINX + 0.002, MAXX - 0.002, 6)):
            for j, y in enumerate(np.linspace(MINY + 0.002, MAXY - 0.002, 5)):
                if (i + j) % 2:
                    continue
                fl = 1 + (i + j) % 5
                s.add(Building(height_m=fl * 3.5, floors=fl,
                               building_type=["residential", "commercial", "school"][(i + j) % 3],
                               land_use="mixed", confidence=0.95,
                               population_estimate=fl * 8, risk_score=0.05,
                               geometry=wkb(MultiPolygon([box(x, y, x + 0.00035, y + 0.00035)])),
                               source="seed"))

        # --- hard constraint: flood zone in the NE corner ---
        s.add(PlanningConstraint(
            type="FLOOD_ZONE", severity="HIGH", source="seed-planning",
            geometry=wkb(MultiPolygon([box(73.1450, 19.0000, MAXX, MAXY)]))))
        s.add(WaterBody(type="stream", seasonality="seasonal", source="seed",
                        geometry=wkb(MultiPolygon([box(73.1300, 18.9960, 73.1320, 18.9980)]))))

    from app.models import Road as R
    from sqlalchemy import func, select
    with session_scope() as s:
        return {n: int(s.execute(select(func.count()).select_from(m)).scalar_one())
                for n, m in [("roads", Road), ("parcels", LandParcel),
                             ("facilities", Facility), ("buildings", Building),
                             ("population_zones", PopulationZone),
                             ("constraints", PlanningConstraint)]}


if __name__ == "__main__":
    print("seeded:", seed())
