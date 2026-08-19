"""Optimization service orchestrating P-Median and Max Coverage solvers over live PostGIS data."""
from __future__ import annotations

from typing import Any
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..engines.contracts import Provenance
from ..engines.gis.distance import distance_matrix
from ..engines.optimization.facility_location import solve_facility_location, solve_max_coverage
from ..engines.optimization.problem_spec import FacilityLocationProblem
from ..repositories import ResultsRepository, SpatialRepository


class OptimizationService:
    def __init__(self, session: Session):
        self.s = session
        self.spatial = SpatialRepository(session)
        self.results = ResultsRepository(session)
        self.cfg = get_settings()

    def optimize_facility_locations(
        self,
        facility_type: str = "hospital",
        objective: str = "max_coverage",
        num_facilities: int = 3,
        scenario_id: int | None = None
    ) -> dict[str, Any]:
        """Perform facility location optimization using OR-Tools CP-SAT solver or deterministic greedy solver."""
        parcels = self.spatial.parcels()
        zones = self.spatial.population_zones()

        cand_ids = [str(getattr(p, "id", f"p_{i+1}")) for i, p in enumerate(parcels)]
        demand_ids = [str(getattr(z, "id", f"z_{i+1}")) for i, z in enumerate(zones)]
        demand_weights = [float(getattr(z, "population", 1000) or 1000) for z in zones]

        if not cand_ids or not demand_ids:
            return {
                "result_id": f"res_opt_{facility_type.lower()}",
                "title": f"Facility Optimization - {facility_type} ({objective.upper()})",
                "objective": objective,
                "facility_type": facility_type,
                "facilities_opened": 0,
                "entities": [],
                "metrics": [
                    {"key": "coverage_ratio", "label": "Population Coverage", "value": 0.0, "unit": "ratio"}
                ],
                "explanation": "No candidate parcels or population demand zones were found in database."
            }

        cand_geoms = [p.geometry for p in parcels]
        demand_geoms = [z.geometry for z in zones]
        cost_mat = distance_matrix(demand_geoms, cand_geoms)

        prob = FacilityLocationProblem(
            candidate_ids=cand_ids,
            demand_ids=demand_ids,
            demand_weights=demand_weights,
            cost_matrix=cost_mat,
            p=min(num_facilities, len(cand_ids)),
            max_cost=15000.0 if objective == "max_coverage" else None
        )

        prov = Provenance(
            dataset_version=self.cfg.dataset_version,
            algorithm="optimization.facility_location",
            algorithm_version="0.1.0",
            scenario_id=str(scenario_id) if scenario_id else None,
            analysis_srid=self.cfg.analysis_srid,
            parameters={"facility_type": facility_type, "objective": objective, "num_facilities": num_facilities}
        )

        if objective == "max_coverage":
            eng_res = solve_max_coverage(prob, prov)
        else:
            eng_res = solve_facility_location(prob, prov)

        out = eng_res.to_dict()
        summary = out.get("summary_metrics", {})

        cov_val = summary.get("coverage_ratio", {}).get("value")
        served_val = summary.get("demand_served", {}).get("value")
        cost_val = summary.get("mean_cost_per_demand_unit", {}).get("value")

        selected_sites = []
        for r in out.get("records", []):
            if "selected_sites" in r:
                selected_sites.extend(r["selected_sites"])

        entities = []
        for site_id in selected_sites:
            entities.append({
                "id": str(site_id),
                "label": f"{facility_type.capitalize()} Site ({site_id})",
                "parcel_id": str(site_id),
                "score": None,
                "metrics": {
                    "coverage_ratio": cov_val,
                    "demand_served": served_val,
                    "mean_cost_per_demand_unit": cost_val
                }
            })

        out["result_id"] = f"res_opt_{facility_type.lower()}_{num_facilities}"
        out["title"] = f"Facility Optimization - {facility_type} ({objective.upper()})"
        out["objective"] = objective
        out["facility_type"] = facility_type
        out["facilities_opened"] = len(selected_sites)
        out["entities"] = entities

        return out
