"""Candidate generation and metric computation. ARCHITECTURE §14.2."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from ..gis.aggregation import population_within
from ..gis.distance import k_nearest_facilities, min_distance_to_any


@dataclass
class Candidate:
    """A parcel that survived hard filtering, plus its computed metrics."""

    id: str
    parcel_id: str
    geometry: Any
    metrics: dict[str, float | None] = field(default_factory=dict)
    soft_penalty: float = 0.0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.id,
            "parcel_id": self.parcel_id,
            "metrics": self.metrics,
            "soft_penalty": round(self.soft_penalty, 6),
            "notes": self.notes,
        }


def generate_candidates(
    parcels: Sequence[Any],
    population_zones: Sequence[Any] = (),
    existing_facilities: Sequence[Any] = (),
    facility_type: str | None = None,
    service_radius: float = 2000.0,
    penalties: dict[str, float] | None = None,
    graph: Any = None,
    travel_time_cutoff: float = 900.0,
) -> list[Candidate]:
    """Build scored-ready candidates from surviving parcels.

    Metrics produced:
      population_served      — population inside the service radius
      travel_time_mean       — mean network time to served zones (if graph given)
      distance_to_same_type  — metres to the nearest same-type facility
      flood_risk, slope, area
    """
    penalties = penalties or {}
    same_type = [
        f for f in existing_facilities
        if facility_type is None or getattr(f, "type", None) == facility_type
    ]

    # Travel times are computed ONCE for all parcels.
    # Previously this ran inside the per-parcel loop, so the same
    # zone-to-everywhere Dijkstra was recomputed for every candidate:
    # 107 parcels x 99 zones = 10,593 searches instead of 99.
    tt_columns: list[list[float | None]] | None = None
    if graph is not None and population_zones and parcels:
        from ..network.routing import travel_time_matrix
        origins = [z.geometry.representative_point() for z in population_zones]
        centroids = [p.geometry.centroid for p in parcels]
        tt_columns = travel_time_matrix(
            graph, origins, centroids, cutoff_seconds=travel_time_cutoff)

    out: list[Candidate] = []
    for p_idx, p in enumerate(parcels):
        centroid = p.geometry.centroid
        ring = centroid.buffer(service_radius)
        pop, assumptions = population_within(ring, population_zones) if population_zones else (0.0, [])

        dist_same = min_distance_to_any(centroid, [f.geometry for f in same_type]) \
            if same_type else None

        tt_mean: float | None = None
        if tt_columns is not None:
            col = [[row[p_idx]] for row in tt_columns]
            vals = [row[0] for row in col if row[0] is not None and row[0] <= travel_time_cutoff]
            weights = [
                float(z.population or 0.0)
                for z, row in zip(population_zones, col)
                if row[0] is not None and row[0] <= travel_time_cutoff
            ]
            wsum = sum(weights)
            if vals and wsum > 0:
                tt_mean = sum(v * w for v, w in zip(vals, weights)) / wsum
            elif vals:
                tt_mean = sum(vals) / len(vals)

        c = Candidate(
            id=f"cand-{p.id}",
            parcel_id=str(p.id),
            geometry=p.geometry,
            metrics={
                "population_served": round(pop, 2),
                "travel_time_mean": None if tt_mean is None else round(tt_mean, 2),
                "distance_to_same_type": None if dist_same is None else round(dist_same, 2),
                "flood_risk": p.flood_risk,
                "slope": p.slope,
                "area": round(float(p.area if p.area is not None else p.geometry.area), 2),
            },
            soft_penalty=float(penalties.get(str(p.id), 0.0)),
            notes=list(assumptions),
        )
        out.append(c)
    return out
