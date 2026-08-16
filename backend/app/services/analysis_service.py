"""Accessibility and infrastructure analysis. ARCHITECTURE §5, §13, §17."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..engines.contracts import Provenance
from ..engines.network import (
    accessibility_metrics, build_graph, emergency_response,
    population_to_facility,
)
from ..engines.simulation import (
    GrowthAssumptions, demand_vs_capacity, project_population,
    resilience_analysis,
)
from ..repositories import ResultsRepository, SpatialRepository


class AnalysisService:
    def __init__(self, session: Session):
        self.s = session
        self.repo = SpatialRepository(session)
        self.results = ResultsRepository(session)
        self.cfg = get_settings()

    def _prov(self, algorithm: str, params: dict[str, Any],
              scenario_id: int | None = None) -> Provenance:
        return Provenance(
            dataset_version=self.cfg.dataset_version,
            algorithm=algorithm, algorithm_version="0.1.0",
            scenario_id=None if scenario_id is None else str(scenario_id),
            analysis_srid=self.cfg.analysis_srid,
            parameters=params,
            source_references=["postgis:roads", "postgis:facilities",
                               "postgis:population_zones"],
        )

    def _graph(self, bbox=None, mode: str = "car"):
        roads = self.repo.roads(bbox=bbox)
        if not roads:
            return None
        return build_graph(roads, mode=mode)

    def accessibility(
        self, facility_type: str = "hospital",
        threshold_seconds: float = 900.0,
        bbox: tuple[float, float, float, float] | None = None,
        scenario_id: int | None = None, persist: bool = True,
    ) -> dict[str, Any]:
        G = self._graph(bbox)
        if G is None:
            return {"error": "no road data available for the requested extent"}
        res = accessibility_metrics(
            G, self.repo.facilities(facility_type=facility_type),
            self.repo.population_zones(bbox=bbox),
            self._prov("network.accessibility", {
                "facility_type": facility_type,
                "threshold_seconds": threshold_seconds,
                "bbox": list(bbox) if bbox else None}, scenario_id),
            threshold_seconds=threshold_seconds,
        )
        out = res.to_dict()
        if persist:
            out["result_id"] = self.results.save(res, scenario_id)
            self.s.commit()
        return out

    def emergency_coverage(
        self, response_seconds: float = 480.0,
        scenario_id: int | None = None, persist: bool = True,
    ) -> dict[str, Any]:
        G = self._graph(mode="emergency")
        if G is None:
            return {"error": "no road data available"}
        res = emergency_response(
            G, self.repo.facilities(facility_type="fire_station"),
            self.repo.population_zones(),
            self._prov("network.emergency_response",
                       {"response_seconds": response_seconds}, scenario_id),
            response_threshold_seconds=response_seconds,
        )
        out = res.to_dict()
        if persist:
            out["result_id"] = self.results.save(res, scenario_id)
            self.s.commit()
        return out

    def facility_assignment(
        self, facility_type: str = "hospital",
        respect_capacity: bool = True,
        scenario_id: int | None = None, persist: bool = True,
    ) -> dict[str, Any]:
        G = self._graph()
        if G is None:
            return {"error": "no road data available"}
        res = population_to_facility(
            G, self.repo.facilities(facility_type=facility_type),
            self.repo.population_zones(),
            self._prov("network.facility_assignment",
                       {"facility_type": facility_type,
                        "respect_capacity": respect_capacity}, scenario_id),
            respect_capacity=respect_capacity,
        )
        out = res.to_dict()
        if persist:
            out["result_id"] = self.results.save(res, scenario_id)
            self.s.commit()
        return out

    def infrastructure_demand(
        self, facility_type: str = "hospital",
        horizon_year: int | None = None, annual_rate: float = 0.025,
        base_year: int = 2025,
        scenario_id: int | None = None, persist: bool = True,
    ) -> dict[str, Any]:
        zones = self.repo.population_zones()
        projected = None
        if horizon_year:
            growth = project_population(
                zones, GrowthAssumptions(base_year, horizon_year, annual_rate),
                self._prov("simulation.population_growth",
                           {"base_year": base_year, "horizon_year": horizon_year,
                            "annual_rate": annual_rate}, scenario_id))
            projected = {r["zone_id"]: r["population_projected"]
                         for r in growth.records}
        res = demand_vs_capacity(
            zones, self.repo.facilities(), facility_type,
            self._prov("simulation.infrastructure_demand",
                       {"facility_type": facility_type,
                        "horizon_year": horizon_year}, scenario_id),
            projected_population=projected,
        )
        out = res.to_dict()
        if persist:
            out["result_id"] = self.results.save(res, scenario_id)
            self.s.commit()
        return out

    def resilience(self, scenario_id: int | None = None,
                   persist: bool = True) -> dict[str, Any]:
        G = self._graph()
        if G is None:
            return {"error": "no road data available"}
        res = resilience_analysis(
            G, self._prov("simulation.resilience", {}, scenario_id),
            facilities=self.repo.facilities())
        out = res.to_dict()
        if persist:
            out["result_id"] = self.results.save(res, scenario_id)
            self.s.commit()
        return out
