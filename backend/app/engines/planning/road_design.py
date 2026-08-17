"""Proposed road alignment validation. ARCHITECTURE §14, §20 (design_road)."""
from __future__ import annotations

from typing import Any, Sequence

from shapely.geometry import LineString

from ..contracts import Road
from ..gis.constraints import ConstraintReport

DEFAULT_LANE_WIDTH = 3.5
CAPACITY_PER_LANE = {
    "motorway": 2000.0, "trunk": 1800.0, "primary": 1500.0, "arterial": 1500.0,
    "secondary": 1200.0, "collector": 1000.0, "tertiary": 900.0,
    "residential": 600.0, "local": 600.0, "service": 300.0,
}


def validate_alignment(
    alignment: Any,
    constraints: Sequence[Any] = (),
    buildings: Sequence[Any] = (),
    min_length: float = 10.0,
) -> ConstraintReport:
    """Check a proposed alignment against hard constraints and structures."""
    rep = ConstraintReport(entity_id="proposed_alignment")

    if alignment is None or alignment.is_empty:
        rep.fail("geometry_present", True, False)
        return rep
    if alignment.geom_type != "LineString":
        rep.fail("geometry_type", "LineString", alignment.geom_type)
        return rep

    length = float(alignment.length)
    (rep.ok if length >= min_length else rep.fail)("min_length", min_length, round(length, 2))

    if not alignment.is_simple:
        rep.fail("self_intersection", "none", "alignment self-intersects")
    else:
        rep.ok("self_intersection", "none", "ok")

    for c in constraints:
        cg = c.geometry.buffer(c.buffer) if getattr(c, "buffer", 0) else c.geometry
        if alignment.intersects(cg):
            overlap = alignment.intersection(cg).length
            if c.severity == "hard":
                rep.fail(f"constraint:{c.type}", "no crossing", round(overlap, 2))
            else:
                rep.soft_penalty += float(c.weight)

    hit = [b for b in buildings if alignment.intersects(b.geometry)]
    if hit:
        rep.fail("building_displacement", 0, len(hit), severity="soft")
        rep.failed[-1]["displaced_building_ids"] = [str(b.id) for b in hit][:50]
    else:
        rep.ok("building_displacement", 0, 0)

    return rep


def road_from_alignment(
    alignment: Any,
    road_id: str,
    road_class: str = "collector",
    lanes: int = 2,
    speed: float | None = None,
    oneway: bool = False,
) -> Road:
    """Turn a drawn alignment into a Road record with derived attributes."""
    from ..network.graph_builder import DEFAULT_SPEEDS
    return Road(
        id=road_id,
        geometry=alignment,
        road_class=road_class,
        width=lanes * DEFAULT_LANE_WIDTH,
        lanes=lanes,
        speed=float(speed or DEFAULT_SPEEDS.get(road_class, 30.0)),
        capacity=lanes * CAPACITY_PER_LANE.get(road_class, 600.0),
        oneway=oneway,
    )
