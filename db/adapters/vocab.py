"""Vocabulary translation between the PostGIS schema and engine contracts.

ARCHITECTURE §8 (attribute normalization), §12.

The database uses its own attribute vocabulary (severity 'HIGH', road_class
'residential', facility type 'clinic'). The engines use a normalized one
(severity 'hard'/'soft'). Every mapping lives here so neither side has to
know about the other.
"""
from __future__ import annotations

from typing import Any

# --- constraint severity -------------------------------------------------
# schema.sql: severity VARCHAR(50) DEFAULT 'HIGH'
# engines: Severity.HARD / Severity.SOFT
SEVERITY_MAP: dict[str, str] = {
    "HIGH": "hard",
    "CRITICAL": "hard",
    "SEVERE": "hard",
    "PROHIBITED": "hard",
    "MEDIUM": "soft",
    "LOW": "soft",
    "ADVISORY": "soft",
    # already-normalized values pass through
    "hard": "hard",
    "soft": "soft",
}

# Soft-constraint penalty weight by database severity.
SEVERITY_WEIGHT: dict[str, float] = {
    "MEDIUM": 0.5, "LOW": 0.2, "ADVISORY": 0.1, "soft": 0.3,
}

# Outward buffer (metres) applied before testing a constraint.
CONSTRAINT_BUFFER: dict[str, float] = {
    "CRZ": 100.0,           # Coastal Regulation Zone
    "FLOOD_ZONE": 0.0,
    "ECO_SENSITIVE": 50.0,
    "WATER_BODY": 30.0,
}


def normalize_severity(value: Any) -> str:
    """Map a database severity to 'hard' or 'soft'. Unknown values are HARD.

    Failing safe matters: an unrecognised constraint must block a site rather
    than silently permit it.
    """
    if value is None:
        return "hard"
    return SEVERITY_MAP.get(str(value).strip(), "hard")


def severity_weight(value: Any) -> float:
    return SEVERITY_WEIGHT.get(str(value).strip(), 1.0)


def constraint_buffer(constraint_type: Any) -> float:
    return CONSTRAINT_BUFFER.get(str(constraint_type).strip().upper(), 0.0)


# --- road classes --------------------------------------------------------
# OSM highway values -> engine road_class (see engines/network/graph_builder).
ROAD_CLASS_MAP: dict[str, str] = {
    "motorway": "motorway", "motorway_link": "motorway",
    "trunk": "trunk", "trunk_link": "trunk",
    "primary": "primary", "primary_link": "primary",
    "secondary": "secondary", "secondary_link": "secondary",
    "tertiary": "tertiary", "tertiary_link": "tertiary",
    "residential": "residential", "living_street": "residential",
    "unclassified": "local", "road": "local",
    "service": "service", "track": "service",
    "footway": "footway", "path": "footway", "pedestrian": "footway",
    "cycleway": "footway", "steps": "footway",
}


def normalize_road_class(value: Any) -> str:
    if value is None:
        return "local"
    v = str(value).strip().lower()
    return ROAD_CLASS_MAP.get(v, "local")


# --- facility types ------------------------------------------------------
# OSM amenity values -> engine facility type used by suitability profiles.
FACILITY_TYPE_MAP: dict[str, str] = {
    "hospital": "hospital",
    "clinic": "clinic",
    "doctors": "clinic",
    "public_hospital": "hospital",
    "school": "school",
    "college": "school",
    "university": "school",
    "kindergarten": "school",
    "fire_station": "fire_station",
    "police": "police",
}


def normalize_facility_type(value: Any) -> str:
    if value is None:
        return "generic"
    return FACILITY_TYPE_MAP.get(str(value).strip().lower(), str(value).strip().lower())


# --- land use / zoning ---------------------------------------------------
LAND_USE_MAP: dict[str, str] = {
    "residential": "residential",
    "commercial": "commercial",
    "mixed_use": "mixed_use",
    "mixed": "mixed_use",
    "public_civic": "institutional",
    "institutional": "institutional",
    "green_space": "green_space",
    "industrial": "industrial",
    "unassigned": "unassigned",
}


def normalize_land_use(value: Any) -> str:
    if value is None:
        return "unassigned"
    return LAND_USE_MAP.get(str(value).strip().lower(), str(value).strip().lower())


def zoning_permits(zoning: Any, facility_type: str) -> bool:
    """Whether a zoning string permits a facility type.

    schema.sql zoning values are descriptive strings such as
    'R-1 Low Density' or 'Public Utility'.
    """
    if zoning is None:
        return False
    z = str(zoning).strip().lower()
    if facility_type in ("hospital", "clinic", "school", "fire_station", "police"):
        return any(k in z for k in ("public", "utility", "civic", "c-1",
                                    "commercial", "mixed", "institution"))
    return True
