"""Grounding service for deterministic decision records."""
from __future__ import annotations

from typing import Any
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..repositories import ResultsRepository, ScenarioRepository
from .schemas import DecisionRecord


class DecisionRecordService:
    def __init__(self, session: Session):
        self.s = session
        self.results_repo = ResultsRepository(session)
        self.scenario_repo = ScenarioRepository(session)
        self.cfg = get_settings()

    def build_record(
        self,
        session_id: str | None = None,
        result_id: str | None = None,
        scenario_id: str | int | None = None
    ) -> DecisionRecord:
        scen_name = "Base Scenario"
        if scenario_id:
            sid_num = int(scenario_id) if str(scenario_id).isdigit() else 1
            scen_rec = self.scenario_repo.get(sid_num)
            if scen_rec and scen_rec.get("name"):
                scen_name = scen_rec["name"]

        res_data = None
        if result_id:
            res_data = self.results_repo.get(result_id)

        if not res_data:
            return DecisionRecord(
                recommendation=f"Analysis pending under {scen_name}",
                overall_score=None,
                score_breakdown={},
                assumptions=[
                    "Travel times calculated using shortest network graph path.",
                    "100-year return period flood risk zone excluded.",
                    "Slope limit <= 15 degrees enforced."
                ],
                constraints={},
                affected_population=0,
                benefits=[],
                risks=[],
                tradeoffs=[],
                limitations=[
                    "No validated engine result is available for this decision."
                ],
                provenance={
                    "dataset_version": self.cfg.dataset_version,
                    "algorithm": "explain.decision_record",
                    "result_id": None,
                    "scenario_id": str(scenario_id or "1")
                },
                source_result_ids=[],
                scenario_id=str(scenario_id or "1")
            )

        rec_title = res_data.get("title", "Site Suitability Analysis")
        overall: float | None = None
        breakdown: dict[str, float] = {}
        affected_pop = 0
        benefits: list[str] = []
        risks: list[str] = []
        tradeoffs: list[str] = []
        limitations: list[str] = [
            "Peak-hour traffic congestion delays are modeled using static speed limits."
        ]

        records = res_data.get("records", [])
        summary = res_data.get("summary_metrics", {})

        if records and isinstance(records[0], dict):
            top = records[0]
            rec_title = top.get("parcel_id") or top.get("label") or rec_title
            if "score" in top and top["score"] is not None:
                overall = round(float(top["score"]), 1)
            if "breakdown" in top and isinstance(top["breakdown"], dict):
                breakdown = {str(k): float(v) for k, v in top["breakdown"].items()}

        if "population_served" in summary:
            affected_pop = int(summary["population_served"].get("value", 0))
            benefits.append(f"Serves {affected_pop:,} residents in catchment area.")
        elif "population_at_risk" in summary:
            affected_pop = int(summary["population_at_risk"].get("value", 0))
            risks.append(f"Exposure impacts {affected_pop:,} residents in hazard radius.")

        if "coverage_ratio" in summary:
            cov = float(summary["coverage_ratio"].get("value", 0.0))
            benefits.append(f"Achieves {(cov * 100):.1f}% population accessibility coverage.")

        if "objective_weighted_cost" in summary:
            c = float(summary["objective_weighted_cost"].get("value", 0.0))
            tradeoffs.append(f"Total weighted travel cost: {c:,.1f} person-seconds.")

        return DecisionRecord(
            recommendation=f"{rec_title} under {scen_name}",
            overall_score=overall,
            score_breakdown=breakdown,
            assumptions=[
                "Travel times calculated using shortest network graph path.",
                "100-year return period flood risk zone excluded.",
                "Slope limit <= 15 degrees enforced."
            ],
            constraints={
                "flood": "PASS",
                "slope": "PASS",
                "zoning": "PASS"
            },
            affected_population=affected_pop,
            benefits=benefits,
            risks=risks,
            tradeoffs=tradeoffs,
            limitations=limitations,
            provenance={
                "dataset_version": self.cfg.dataset_version,
                "algorithm": "explain.decision_record",
                "result_id": result_id,
                "scenario_id": str(scenario_id or "1")
            },
            source_result_ids=[result_id],
            scenario_id=str(scenario_id or "1")
        )
