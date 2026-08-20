"""City scoring, packages and guided scenarios. Product report §1-§3.

Follows the same contract as the other services: repositories load domain
records, deterministic engines do the maths, this layer only orchestrates
and attaches provenance.

Regional scoping matters here. The canonical tables hold the pilot sector;
the three comparison areas live in `{region}_*` tables. Scoring a benchmark
city therefore reads through a different path than scoring the pilot, and
the result records which was used so the UI never implies a measurement it
did not make.
"""
from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..engines.contracts import Provenance
from ..engines.scoring.benchmarks import benchmark_for, reference_values
from ..engines.scoring.city_score import (ALGORITHM, ALGORITHM_VERSION,
                                          score_city, scorecard_payload)
from ..engines.scoring.dimensions import PROFILE_VERSION, profile_from_weights
from ..engines.scoring.package import generate_package
from ..repositories import ResultsRepository, SpatialRepository

PILOT = "adivali_devad"


class ScoringService:
    def __init__(self, session: Session):
        self.s = session
        self.repo = SpatialRepository(session)
        self.results = ResultsRepository(session)
        self.cfg = get_settings()

    # ------------------------------------------------------------------
    # data loading
    # ------------------------------------------------------------------
    def _provenance(self, region: str, weights: dict[str, float] | None,
                    extra: dict[str, Any] | None = None) -> Provenance:
        return Provenance(
            dataset_version=self.cfg.dataset_version,
            algorithm=ALGORITHM,
            algorithm_version=ALGORITHM_VERSION,
            scoring_profile_version=(PROFILE_VERSION + "+custom" if weights
                                     else PROFILE_VERSION),
            analysis_srid=self.cfg.analysis_srid,
            parameters={"region": region, **(extra or {})},
        )

    def _pilot_inputs(self) -> dict[str, Any]:
        """Domain records for the canonical (pilot) tables."""
        return {
            "roads": self.repo.roads(),
            "parcels": self.repo.parcels(),
            "facilities": self.repo.facilities(),
            "population_zones": self.repo.population_zones(),
        }

    def _region_counts(self, region: str) -> dict[str, int]:
        """Row counts for a comparison region's own tables."""
        out: dict[str, int] = {}
        for layer in ("roads", "buildings", "water", "bridges"):
            table = f"{region}_{layer}"
            try:
                exists = self.s.execute(
                    text("SELECT to_regclass(:t)"),
                    {"t": f"public.{table}"}).scalar()
                if not exists:
                    continue
                n = self.s.execute(
                    text(f'SELECT count(*) FROM public."{table}"')).scalar()
                if n:
                    out[layer] = int(n)
            except Exception:                                # noqa: BLE001
                continue
        return out

    def _graph(self, roads: Sequence[Any]):
        if not roads:
            return None
        try:
            from ..engines.network import build_graph
            return build_graph(roads)
        except Exception:                                    # noqa: BLE001
            return None

    def _accessibility(self, graph, facilities, zones, prov):
        if graph is None or not facilities or not zones:
            return None
        try:
            from ..engines.network.accessibility import accessibility_metrics
            return accessibility_metrics(graph, facilities, zones, prov)
        except Exception:                                    # noqa: BLE001
            return None

    # ------------------------------------------------------------------
    # feature 2: city scoring
    # ------------------------------------------------------------------
    def score(self, region: str = PILOT,
              weights: dict[str, float] | None = None,
              persist: bool = False) -> dict[str, Any]:
        region = (region or PILOT).lower().strip()
        prov = self._provenance(region, weights)

        if region == PILOT:
            data = self._pilot_inputs()
            graph = self._graph(data["roads"])
            acc = self._accessibility(graph, data["facilities"],
                                      data["population_zones"], prov)
            bench_raw = reference_values(region)
            bench_source = "published"

            result = score_city(
                region=region,
                roads=data["roads"], parcels=data["parcels"],
                facilities=data["facilities"],
                population_zones=data["population_zones"],
                provenance=prov, accessibility=acc, graph=graph,
                profile=profile_from_weights(weights),
                benchmark_raw=bench_raw,
                benchmark_source=bench_source,
            )
            payload = scorecard_payload(result, region, bench_source)
        else:
            # Comparison regions carry geometry only: roads, buildings,
            # water, bridges. There are no population zones or parcel
            # attributes, so most dimensions are genuinely unmeasurable.
            # Report that rather than fabricating inputs.
            counts = self._region_counts(region)
            prov = self._provenance(region, weights, {"tables": counts})
            result = score_city(
                region=region,
                roads=[], parcels=[], facilities=[], population_zones=[],
                provenance=prov, accessibility=None, graph=None,
                profile=profile_from_weights(weights),
                benchmark_raw=reference_values(region),
                benchmark_source="published",
            )
            payload = scorecard_payload(result, region, "published")
            payload["regionTables"] = counts
            if not counts:
                payload["warnings"] = list(payload.get("warnings", [])) + [
                    f"No extracted tables for '{region}'. Run "
                    f"`python db/extract.py {region}` to populate it."]
            else:
                payload["warnings"] = list(payload.get("warnings", [])) + [
                    f"'{region}' has geometry only ({', '.join(f'{k}: {v}' for k, v in counts.items())}); "
                    "demographic and parcel attributes are not extracted for "
                    "comparison regions, so most dimensions cannot be scored."]

        if persist:
            try:
                self.results.save(result)
            except Exception as exc:                         # noqa: BLE001
                payload["persistError"] = f"{type(exc).__name__}: {exc}"
        return payload

    # ------------------------------------------------------------------
    # feature 1: development package
    # ------------------------------------------------------------------
    def package(self, region: str = PILOT, target_uplift: float = 10.0,
                priorities: Sequence[str] = (),
                budget: float | None = None,
                weights: dict[str, float] | None = None,
                max_actions: int = 12) -> dict[str, Any]:
        region = (region or PILOT).lower().strip()
        card = self.score(region=region, weights=weights)

        prov = self._provenance(region, weights, {
            "target_uplift": target_uplift,
            "priorities": list(priorities),
            "budget": budget,
        })

        data = self._pilot_inputs() if region == PILOT else {
            "roads": [], "parcels": [], "facilities": [],
            "population_zones": []}
        graph = self._graph(data["roads"])

        result = generate_package(
            region=region, scorecard=card, provenance=prov,
            parcels=data["parcels"], population_zones=data["population_zones"],
            facilities=data["facilities"], graph=graph,
            target_uplift=target_uplift, priorities=priorities,
            budget=budget, max_actions=max_actions,
        )

        return {
            "region": region,
            "currentScore": card.get("overallScore"),
            "projectedScore": result.value("projected_score"),
            "expectedUplift": result.value("expected_uplift"),
            "targetUplift": target_uplift,
            "totalCost": result.value("total_cost"),
            "baseCost": result.value("base_cost"),
            "contingency": result.value("contingency"),
            "currency": "INR",
            "actionCount": result.value("actions"),
            "primaryActionCount": result.value("primary_actions"),
            "actions": result.records,
            "warnings": result.warnings,
            "scorecard": card,
            "provenance": result.provenance.to_dict(),
        }

    # ------------------------------------------------------------------
    # feature 3: guided scenarios
    # ------------------------------------------------------------------
    def compare_packages(self, region: str = PILOT,
                         variants: Sequence[dict[str, Any]] = (),
                         weights: dict[str, float] | None = None
                         ) -> dict[str, Any]:
        """Build one package per variant and lay them out side by side.

        Each variant is {name, targetUplift, priorities[], budget}. This is
        report §3 steps 5-6: generate A/B/C, then compare on common KPIs.
        """
        region = (region or PILOT).lower().strip()
        if not variants:
            variants = [
                {"name": "A - Balanced", "targetUplift": 10.0,
                 "priorities": []},
                {"name": "B - Health & education first", "targetUplift": 10.0,
                 "priorities": ["healthcare", "education", "facility_access"]},
                {"name": "C - Mobility & resilience", "targetUplift": 10.0,
                 "priorities": ["mobility", "resilience", "infrastructure"]},
            ]

        card = self.score(region=region, weights=weights)
        out: list[dict[str, Any]] = []
        for v in variants:
            pkg = self.package(
                region=region,
                target_uplift=float(v.get("targetUplift", 10.0)),
                priorities=tuple(v.get("priorities") or ()),
                budget=v.get("budget"),
                weights=weights,
                max_actions=int(v.get("maxActions", 12)),
            )
            cost = pkg.get("totalCost") or 0.0
            uplift = pkg.get("expectedUplift") or 0.0
            out.append({
                "name": v.get("name", "Scenario"),
                "priorities": list(v.get("priorities") or []),
                "budget": v.get("budget"),
                "expectedUplift": uplift,
                "projectedScore": pkg.get("projectedScore"),
                "totalCost": cost,
                "actionCount": pkg.get("actionCount"),
                "primaryActionCount": pkg.get("primaryActionCount"),
                "populationServed": sum(
                    float(a.get("populationServed") or 0.0)
                    for a in pkg.get("actions", [])),
                # The decision metric planners actually argue about.
                "costPerPoint": (round(cost / uplift) if uplift > 0 else None),
                "actions": pkg.get("action", []),
                "warnings": pkg.get("warnings", []),
            })

        ranked = sorted(
            [s for s in out if s["costPerPoint"] is not None],
            key=lambda s: s["costPerPoint"])
        recommended = ranked[0]["name"] if ranked else (
            out[0]["name"] if out else None)

        return {
            "region": region,
            "baseline": {
                "overallScore": card.get("overallScore"),
                "benchmarkScore": card.get("benchmarkScore"),
                "benchmark": card.get("benchmark"),
            },
            "scenarios": out,
            "recommended": recommended,
            "recommendationBasis": (
                "Lowest cost per point of score uplift among scenarios that "
                "produced a measurable improvement."),
        }
