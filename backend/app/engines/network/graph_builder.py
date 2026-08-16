"""Road graph construction. ARCHITECTURE §13.1.

The graph is derived, never hand-maintained. Every build is keyed by
(dataset_version, scenario_version, mode_profile, builder_version) so routing
results are always attributable to an exact input state.
"""
from __future__ import annotations

import hashlib
from typing import Any, Iterable, Mapping, Sequence

import networkx as nx

BUILDER_VERSION = "0.1.0"

# Default speeds (km/h) by road class, used when a segment lacks one.
DEFAULT_SPEEDS: dict[str, float] = {
    "motorway": 80.0, "trunk": 60.0, "primary": 50.0, "arterial": 50.0,
    "secondary": 40.0, "collector": 40.0, "tertiary": 35.0,
    "residential": 25.0, "local": 25.0, "service": 15.0, "footway": 5.0,
}

# Mode profiles: speed multiplier and which classes are traversable.
MODE_PROFILES: dict[str, dict[str, Any]] = {
    "car":       {"factor": 1.0,  "exclude": {"footway"}},
    "emergency": {"factor": 1.3,  "exclude": {"footway"}},
    "walk":      {"factor": 1.0,  "exclude": set(), "fixed_speed": 4.8},
}


def _round_node(coord: tuple[float, float], precision: float = 0.5) -> tuple[float, float]:
    """Snap endpoints to a grid so touching segments share a node."""
    return (round(coord[0] / precision) * precision,
            round(coord[1] / precision) * precision)



def node_roads(roads: Sequence[Any], tolerance: float = 0.01) -> list[Any]:
    """Split road geometries at their mutual intersections (planarize).

    Source data is not guaranteed to be noded: two crossing linestrings may
    share no vertex, which would leave the graph disconnected at that junction.

    Splitting is done by projecting each crossing point onto the line's
    measure (``project``) and rebuilding segments from those distances.
    ``shapely.ops.split`` is deliberately not used: an intersection point that
    is off the line by even 1e-9 (routine after reprojection) makes it return
    the line unsplit, silently producing a disconnected network.
    """
    from shapely.geometry import LineString, Point
    from shapely.strtree import STRtree

    if not roads:
        return []

    geoms = [r.geometry for r in roads]
    tree = STRtree(geoms)
    out: list[Any] = []

    for i, r in enumerate(roads):
        g = geoms[i]
        if g.geom_type != "LineString":
            out.append(r)
            continue

        length = g.length
        # Collect split positions as distances along the line.
        dists: list[float] = []
        for j in tree.query(g):
            j = int(j)
            if j == i:
                continue
            inter = g.intersection(geoms[j])
            if inter.is_empty:
                continue
            pts: list[Any] = []
            if inter.geom_type == "Point":
                pts = [inter]
            elif inter.geom_type == "MultiPoint":
                pts = list(inter.geoms)
            elif inter.geom_type == "LineString":
                pts = [Point(inter.coords[0]), Point(inter.coords[-1])]
            elif inter.geom_type == "MultiLineString":
                for part in inter.geoms:
                    pts.extend([Point(part.coords[0]), Point(part.coords[-1])])
            for p in pts:
                d = g.project(p)
                if tolerance < d < length - tolerance:
                    dists.append(d)

        if not dists:
            out.append(r)
            continue

        # Deduplicate nearby cut positions, then rebuild segments.
        dists = sorted(dists)
        cuts: list[float] = []
        for d in dists:
            if not cuts or (d - cuts[-1]) > tolerance:
                cuts.append(d)

        bounds = [0.0] + cuts + [length]
        piece_no = 0
        for a, b in zip(bounds[:-1], bounds[1:]):
            if (b - a) <= tolerance:
                continue
            seg = _substring(g, a, b)
            if seg is None or seg.length <= tolerance:
                continue
            out.append(_patched(r, {"id": f"{r.id}#{piece_no}", "geometry": seg}))
            piece_no += 1

        if piece_no == 0:          # nothing usable was produced; keep original
            out.append(r)
    return out


def _substring(line: Any, start: float, end: float) -> Any | None:
    """Extract the portion of `line` between two distances along it."""
    from shapely.geometry import LineString, Point

    try:
        from shapely.ops import substring as _shp_substring
        seg = _shp_substring(line, start, end)
        if seg is not None and not seg.is_empty and seg.geom_type == "LineString":
            return seg
    except Exception:
        pass

    # Manual fallback.
    coords = [Point(line.interpolate(start))]
    acc = 0.0
    pts = list(line.coords)
    for a, b in zip(pts[:-1], pts[1:]):
        seg_len = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
        nxt = acc + seg_len
        if nxt > start and acc < end:
            if start < nxt < end:
                coords.append(Point(b))
        acc = nxt
    coords.append(Point(line.interpolate(end)))
    uniq = [(p.x, p.y) for p in coords]
    dedup = [uniq[0]] + [c for prev, c in zip(uniq[:-1], uniq[1:]) if c != prev]
    return LineString(dedup) if len(dedup) >= 2 else None


def build_graph(
    roads: Sequence[Any],
    mode: str = "car",
    snap_precision: float = 0.5,
    node_network: bool = True,
) -> nx.DiGraph:
    """Build a directed road graph from authoritative road records.

    Edge attributes: length (m), speed (km/h), time (s), road_id, road_class.
    Geometry must already be in the projected analysis CRS.
    """
    if mode not in MODE_PROFILES:
        raise ValueError(f"unknown mode profile: {mode}")
    profile = MODE_PROFILES[mode]
    if node_network:
        roads = node_roads(roads)
    G = nx.DiGraph()
    G.graph["mode"] = mode
    G.graph["builder_version"] = BUILDER_VERSION

    for r in roads:
        if r.road_class in profile["exclude"]:
            continue
        coords = list(r.geometry.coords)
        if len(coords) < 2:
            continue

        speed = profile.get("fixed_speed") or (
            r.speed or DEFAULT_SPEEDS.get(r.road_class, 25.0)
        )
        speed = float(speed) * (1.0 if "fixed_speed" in profile else profile["factor"])
        mps = max(speed, 1.0) * 1000.0 / 3600.0

        for a, b in zip(coords[:-1], coords[1:]):
            u, v = _round_node(a, snap_precision), _round_node(b, snap_precision)
            if u == v:
                continue
            length = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
            attrs = {
                "length": length,
                "speed": speed,
                "time": length / mps,
                "road_id": str(r.id),
                "road_class": r.road_class,
                "capacity": r.capacity,
            }
            G.add_edge(u, v, **attrs)
            if not r.oneway:
                G.add_edge(v, u, **attrs)
    return G


def apply_road_deltas(
    base_roads: Sequence[Any],
    added: Sequence[Any] = (),
    removed_ids: Iterable[str] = (),
    modified: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[Any]:
    """Produce the scenario road set. Base list is never mutated (§16)."""
    removed = {str(i) for i in removed_ids}
    modified = modified or {}
    out: list[Any] = []
    for r in base_roads:
        if str(r.id) in removed:
            continue
        patch = modified.get(str(r.id))
        if patch:
            import copy
            r = copy.replace(r, **patch) if hasattr(copy, "replace") else _patched(r, patch)
        out.append(r)
    out.extend(added)
    return out


def _patched(record: Any, patch: Mapping[str, Any]) -> Any:
    """Shallow copy with attribute overrides (py<3.13 fallback)."""
    import copy as _c
    new = _c.copy(record)
    for k, v in patch.items():
        setattr(new, k, v)
    return new


def graph_signature(
    dataset_version: int,
    scenario_version: int | None,
    mode: str,
) -> str:
    """Cache key for a built graph (§13.1)."""
    raw = f"{dataset_version}|{scenario_version}|{mode}|{BUILDER_VERSION}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
