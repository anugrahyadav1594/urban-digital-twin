"""Scenario lifecycle and evaluation. ARCHITECTURE §5, §16, §24.

Base City + Scenario Deltas = Proposed State. The base tables are read-only
for every operation in this service.
"""
from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..engines.comparison import compare_scenarios
from ..engines.contracts import EngineResult, Provenance
from ..engines.network import accessibility_metrics, build_graph
from ..engines.scenario import ResolvedCity, resolve_scenario
from ..engines.simulation import demand_vs_capacity
from ..repositories import ResultsRepository, ScenarioRepository, SpatialRepository


class ScenarioService:
    def __init__(self, session: Session):
        self.s = session
        self.spatial = SpatialRepository(session)
        self.scenarios = ScenarioRepository(session)
        self.results = ResultsRepository(session)
        self.cfg = get_settings()

    # ---------------- lifecycle ----------------
    def create(self, name: str, description: str | None = None) -> dict[str, Any]:
        sid = self.scenarios.create(name, description)
        self.s.commit()
        return {"scenario_id": sid, "name": name, "status": "created"}

    def add_change(self, scenario_id: int, object_type: str, operation: str,
                   parameters: dict[str, Any],
                   object_id: int | None = None) -> dict[str, Any]:
        cid = self.scenarios.add_change(
            scenario_id, object_type, operation, parameters, object_id)
        self.s.commit()
        return {"change_id": cid, "scenario_id": scenario_id, "status": "logged"}

    def list(self) -> list[dict[str, Any]]:
        return self.scenarios.list()

    # ---------------- resolution ----------------
    def resolve(self, scenario_id: int,
                bbox: tuple[float, float, float, float] | None = None
                ) -> ResolvedCity:
        """Materialise the proposed city state in memory. Base is untouched."""
        base = {
            "roads": self.spatial.roads(bbox=bbox),
            "parcels": self.spatial.parcels(bbox=bbox),
            "facilities": self.spatial.facilities(bbox=bbox),
            "population_zones": self.spatial.population_zones(bbox=bbox),
            "buildings": self.spatial.buildings(bbox=bbox),
            "constraints": self.spatial.constraints(bbox=bbox),
        }
        return resolve_scenario(
            base,
            self.scenarios.to_engine_changes(scenario_id),
            dataset_version=self.cfg.dataset_version,
            scenario_id=str(scenario_id),
            scenario_version=1,
        )

    # ---------------- evaluation ----------------
    def evaluate(self, scenario_id: int, facility_type: str = "hospital",
                 threshold_seconds: float = 900.0,
                 persist: bool = True) -> list[EngineResult]:
        """Run the standard metric battery against a resolved scenario."""
        city = self.resolve(scenario_id)
        prov = Provenance(
            dataset_version=self.cfg.dataset_version,
            algorithm="scenario.evaluate", algorithm_version="0.1.0",
            scenario_id=str(scenario_id), scenario_version=1,
            analysis_srid=self.cfg.analysis_srid,
            parameters={"facility_type": facility_type,
                        "threshold_seconds": threshold_seconds},
            source_references=["postgis:scenario_changes"],
        )

        out: list[EngineResult] = []
        facs = [f for f in city.facilities if f.type == facility_type]

        if city.roads:
            G = build_graph(city.roads, mode="car")
            out.append(accessibility_metrics(
                G, facs, city.population_zones, prov,
                threshold_seconds=threshold_seconds))

        out.append(demand_vs_capacity(
            city.population_zones, city.facilities, facility_type, prov))

        if persist:
            for r in out:
                self.results.save(r, scenario_id)
            self.s.commit()
        return out

    # ---------------- comparison (§24) ----------------
    def compare(self, scenario_ids: Sequence[int],
                facility_type: str = "hospital",
                persist: bool = True) -> dict[str, Any]:
        per_scenario = {
            str(sid): self.evaluate(sid, facility_type, persist=False)
            for sid in scenario_ids
        }
        prov = Provenance(
            dataset_version=self.cfg.dataset_version,
            algorithm="comparison.compare_scenarios", algorithm_version="0.1.0",
            analysis_srid=self.cfg.analysis_srid,
            parameters={"scenario_ids": list(scenario_ids),
                        "facility_type": facility_type},
        )
        res = compare_scenarios(per_scenario, prov)
        out = res.to_dict()
        if persist:
            out["result_id"] = self.results.save(res, None)
            self.s.commit()
        return out
