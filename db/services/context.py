"""Analysis context: versioning and shared inputs.

ARCHITECTURE §25. Every service call carries the reproducibility tuple so
each stored result can be re-derived from dataset_version + scenario_version
+ algorithm_version + parameters.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Mapping

from app.engines.contracts import Provenance

from db.adapters.geometry import ANALYSIS_SRID

DATASET_VERSION = int(os.getenv("DATASET_VERSION", "1"))


@dataclass
class AnalysisContext:
    """Shared, versioned inputs for one analysis run."""

    dataset_version: int = DATASET_VERSION
    scenario_id: int | None = None
    scenario_version: int | None = None
    analysis_srid: int = ANALYSIS_SRID
    bbox: tuple[float, float, float, float] | None = None
    parameters: dict[str, Any] = field(default_factory=dict)

    def provenance(
        self,
        algorithm: str,
        algorithm_version: str = "0.1.0",
        extra_parameters: Mapping[str, Any] | None = None,
        scoring_profile_version: str | None = None,
        cost_profile_version: str | None = None,
    ) -> Provenance:
        params = dict(self.parameters)
        if extra_parameters:
            params.update(extra_parameters)
        return Provenance(
            dataset_version=self.dataset_version,
            algorithm=algorithm,
            algorithm_version=algorithm_version,
            scenario_id=str(self.scenario_id) if self.scenario_id else None,
            scenario_version=self.scenario_version,
            scoring_profile_version=scoring_profile_version,
            cost_profile_version=cost_profile_version,
            analysis_srid=self.analysis_srid,
            parameters=params,
            source_references=(
                "postgis:roads", "postgis:buildings", "postgis:land_parcels",
                "postgis:facilities", "postgis:population_zones",
                "postgis:planning_constraints",
            ),
        )
