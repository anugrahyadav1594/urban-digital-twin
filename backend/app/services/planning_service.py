"""Planning / suitability orchestration. ARCHITECTURE §5, §14.

This is the join between storage and the deterministic engines: load domain
records via repositories, run the engine, persist the result with provenance.
No spatial maths happens here.
"""
from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..engines.contracts import Provenance
from ..engines.network import build_graph
from ..engines.planning import DEFAULT_PROFILES, SiteRequirements, site_suitability
from ..repositories import ResultsRepository, SpatialRepository

ALGORITHM = "planning.site_suitability"
ALGORITHM_VERSION = "0.1.0"


class PlanningService:
    def __init__(self, session: Session):
        self.s = session
        self.repo = SpatialRepository(session)
        self.results = ResultsRepository(session)
        self.cfg = get_settings()

    def find_sites(
        self,
        facility_type: str = "hospital",
        top_n: int = 5,
        required_area: float | None = 5000.0,
        max_slope: float | None = 15.0,
        max_flood_risk: float | None = 0.30,
        allowed_zoning: Sequence[str] | None = None,
        min_distance_same_type: float | None = None,
        service_radius: float = 2000.0,
        bbox: tuple[float, float, float, float] | None = None,
        scenario_id: int | None = None,
        use_network: bool = True,
        persist: bool = True,
    ) -> dict[str, Any]:
        """Rank candidate parcels for a new facility, backed by live PostGIS."""
        parcels = self.repo.parcels(bbox=bbox)
        zones = self.repo.population_zones(bbox=bbox)
        existing = self.repo.facilities(facility_type=facility_type)
        constraints = self.repo.constraints(bbox=bbox)

        graph = None
        if use_network:
            roads = self.repo.roads(bbox=bbox)
            if roads:
                graph = build_graph(roads, mode="car")

        profile = DEFAULT_PROFILES.get(facility_type, DEFAULT_PROFILES["hospital"])

        req = SiteRequirements(
            facility_type=facility_type,
            required_area=required_area,
            max_slope=max_slope,
            max_flood_risk=max_flood_risk,
            allowed_zoning=tuple(allowed_zoning or ()),
            allowed_status=(),          # NAGAR-X marks parcels 'candidate'
            min_distance_same_type=min_distance_same_type,
            scoring_profile=profile.name,
        )

        prov = Provenance(
            dataset_version=self.cfg.dataset_version,
            algorithm=ALGORITHM,
            algorithm_version=ALGORITHM_VERSION,
            scenario_id=None if scenario_id is None else str(scenario_id),
            scoring_profile_version=profile.version,
            analysis_srid=self.cfg.analysis_srid,
            parameters={
                "facility_type": facility_type,
                "required_area": required_area,
                "max_slope": max_slope,
                "max_flood_risk": max_flood_risk,
                "allowed_zoning": list(allowed_zoning or ()),
                "min_distance_same_type": min_distance_same_type,
                "service_radius": service_radius,
                "top_n": top_n,
                "bbox": list(bbox) if bbox else None,
                "network_routing": bool(graph is not None),
            },
            source_references=[
                "postgis:land_parcels", "postgis:population_zones",
                "postgis:facilities", "postgis:planning_constraints",
            ] + (["postgis:roads"] if graph is not None else []),
        )

        result = site_suitability(
            parcels=parcels,
            requirements=req,
            provenance=prov,
            constraints=constraints,
            population_zones=zones,
            existing_facilities=existing,
            graph=graph,
            profile=profile,
            service_radius=service_radius,
            top_n=top_n,
        )

        payload = result.to_dict()
        if persist:
            payload["result_id"] = self.results.save(result, scenario_id)
            self.s.commit()
        return payload
