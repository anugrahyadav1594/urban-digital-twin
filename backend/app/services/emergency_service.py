"""Emergency routing and disaster simulation orchestration. ARCHITECTURE §13, §17.

Loads spatial data, projects incident coordinates into the analysis CRS, runs
the engines and persists results. Engines stay pure; all I/O lives here.
"""
from __future__ import annotations

from typing import Any, Sequence

from shapely.geometry import Point
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..engines.contracts import Provenance
from ..engines.crs import to_analysis, to_storage
from ..engines.network import build_graph
from ..engines.network.emergency_routing import (
    DEFAULT_TURNOUT_SECONDS, compare_routes, degrade_graph, route_to_incident)
from ..engines.simulation.disaster import (
    HAZARD_TYPES, MEASURES, build_hazard, compare_measures, simulate_disaster)
from ..repositories import ResultsRepository, SpatialRepository


class EmergencyService:
    """Emergency response routing and disaster scenario simulation."""

    def __init__(self, session: Session):
        self.s = session
        self.cfg = get_settings()
        self.repo = SpatialRepository(session)
        self.results = ResultsRepository(session)

    # ------------------------------------------------------------------
    def _prov(self, algorithm: str, params: dict[str, Any],
              scenario_id: int | None = None) -> Provenance:
        return Provenance(
            dataset_version=self.cfg.dataset_version,
            algorithm=algorithm, algorithm_version="0.1.0",
            scenario_id=None if scenario_id is None else str(scenario_id),
            analysis_srid=self.cfg.analysis_srid,
            parameters=params,
            source_references=["postgis:roads", "postgis:facilities",
                               "postgis:buildings", "postgis:population_zones"],
        )

    def _point(self, lon: float, lat: float) -> Any:
        """lon/lat -> analysis CRS metres. Engines never see degrees."""
        return to_analysis(Point(float(lon), float(lat)), self.cfg.analysis_srid)

    def _to_lonlat_path(self, path: Sequence[Sequence[float]]) -> list[list[float]]:
        out = []
        for x, y in path:
            p = to_storage(Point(float(x), float(y)), self.cfg.analysis_srid)
            out.append([round(p.x, 6), round(p.y, 6)])
        return out

    # ------------------------------------------------------------------
    def find_route(
        self,
        lon: float,
        lat: float,
        responder_type: str = "fire_station",
        top_n: int = 3,
        turnout_seconds: float = DEFAULT_TURNOUT_SECONDS,
        response_target_seconds: float = 480.0,
        blocked_road_ids: Sequence[str] = (),
        slowed_road_ids: Sequence[str] = (),
        scenario_id: int | None = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        """Best routes from responding stations to an incident."""
        roads = self.repo.roads()
        if not roads:
            return {"error": "no road data available"}
        stations = self.repo.facilities(facility_type=responder_type)
        if not stations:
            return {"error": f"no '{responder_type}' facilities in the database"}

        G = build_graph(roads, mode="emergency")
        stats = {}
        if blocked_road_ids or slowed_road_ids:
            G, stats = degrade_graph(
                G, blocked_road_ids=blocked_road_ids,
                slowed_road_ids=slowed_road_ids)

        prov = self._prov("network.emergency_routing", {
            "incident": [lon, lat], "responder_type": responder_type,
            "top_n": top_n, "turnout_seconds": turnout_seconds,
            "response_target_seconds": response_target_seconds,
            "blocked_road_ids": list(blocked_road_ids) or None,
            "slowed_road_ids": list(slowed_road_ids) or None,
        }, scenario_id)

        res = route_to_incident(
            G, self._point(lon, lat), stations, prov, top_n=top_n,
            turnout_seconds=turnout_seconds,
            response_target_seconds=response_target_seconds)

        out = res.to_dict()
        # Paths are metres internally; the map needs lon/lat.
        for rec in out.get("records", []):
            if rec.get("path"):
                rec["path"] = self._to_lonlat_path(rec["path"])
        if stats:
            out.setdefault("network", {}).update(stats)
        if persist:
            try:
                out["result_id"] = self.results.save(res, scenario_id)
                self.s.commit()
            except Exception as exc:                     # noqa: BLE001
                self.s.rollback()
                out["persist_error"] = f"{type(exc).__name__}: {exc}"
        return out

    # ------------------------------------------------------------------
    def simulate(
        self,
        hazard_type: str,
        lon: float,
        lat: float,
        radius_m: float | None = None,
        intensity: float = 1.0,
        measures: Sequence[str] = (),
        responder_type: str | None = None,
        response_target_seconds: float = 480.0,
        include_routing: bool = True,
        scenario_id: int | None = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        """Run a disaster twice — without and with measures — and compare.

        Returns exposure for both, the measure-by-measure delta, and (when
        routing is on) what the event does to emergency response times.
        """
        spec = HAZARD_TYPES.get(hazard_type)
        if spec is None:
            return {"error": f"unknown hazard type '{hazard_type}'",
                    "supported": sorted(HAZARD_TYPES)}
        unknown = [m for m in measures if m not in MEASURES]
        if unknown:
            return {"error": f"unknown measure(s): {', '.join(unknown)}",
                    "supported": sorted(MEASURES)}

        centre = self._point(lon, lat)
        buildings = self.repo.buildings()
        zones = self.repo.population_zones()
        facilities = self.repo.facilities()
        roads = self.repo.roads()

        params = {"hazard_type": hazard_type, "center": [lon, lat],
                  "radius_m": radius_m, "intensity": intensity,
                  "measures": list(measures)}
        prov = self._prov("simulation.disaster", params, scenario_id)

        base_h = build_hazard(hazard_type, centre, radius_m, intensity, ())
        base = simulate_disaster(base_h, prov, buildings=buildings,
                                 population_zones=zones, facilities=facilities,
                                 roads=roads)

        mit_h = build_hazard(hazard_type, centre, radius_m, intensity, measures)
        mit = simulate_disaster(mit_h, prov, buildings=buildings,
                                population_zones=zones, facilities=facilities,
                                roads=roads)

        comparison = compare_measures(base, mit, prov)

        out: dict[str, Any] = {
            "hazard": {
                "type": hazard_type, "label": spec["label"],
                "center": [lon, lat],
                "radius_m": round(base_h.radius_m, 1),
                "radius_m_mitigated": round(mit_h.radius_m, 1),
                "intensity": base_h.intensity,
                "measures": list(mit_h.measures),
                "footprint": self._footprint_lonlat(base_h),
                "footprint_mitigated": self._footprint_lonlat(mit_h),
            },
            "baseline": base.to_dict(),
            "mitigated": mit.to_dict(),
            "comparison": comparison.to_dict(),
        }

        if include_routing:
            # Exposure numbers are the primary product; response routing is an
            # add-on over a much larger graph. A failure there used to 500 the
            # whole request and the panel reported "simulation failed" even
            # though every exposure figure had already been computed.
            try:
                out["response"] = self._response_impact(
                    base, mit, roads, lon, lat,
                    responder_type or spec["responder_type"],
                    response_target_seconds, scenario_id)
            except Exception as exc:                     # noqa: BLE001
                out["response"] = {
                    "error": f"response routing failed: {type(exc).__name__}: {exc}",
                    "responder_type": responder_type or spec["responder_type"],
                }

        # Blocked/slowed roads as map geometry, so the disruption is visible
        # rather than just a count in a table.
        out["network"] = self._network_impact_geometry(base, mit, roads)

        if persist:
            # A results-table problem must not discard a completed simulation.
            try:
                out["result_id"] = self.results.save(mit, scenario_id)
                self.s.commit()
            except Exception as exc:                     # noqa: BLE001
                self.s.rollback()
                out["persist_error"] = f"{type(exc).__name__}: {exc}"
        return out

    # ------------------------------------------------------------------
    def _network_impact_geometry(
        self, base: Any, mit: Any, roads: Sequence[Any],
    ) -> dict[str, Any]:
        """Blocked and slowed roads as lon/lat lines for the map."""
        b_block, b_slow = self._blocked_from(base)
        m_block, _ = self._blocked_from(mit)
        by_id = {str(r.id): r for r in roads}
        m_set = set(m_block)

        def lines(ids: Sequence[str], limit: int = 400) -> list[list[list[float]]]:
            out: list[list[list[float]]] = []
            for rid in list(ids)[:limit]:
                r = by_id.get(str(rid))
                g = getattr(r, "geometry", None) if r is not None else None
                if g is None or g.is_empty:
                    continue
                try:
                    ls = to_storage(g, self.cfg.analysis_srid)
                except Exception:                        # noqa: BLE001
                    continue
                if ls.geom_type == "LineString":
                    out.append([[round(x, 6), round(y, 6)] for x, y in ls.coords])
            return out

        return {
            "blocked_count": len(b_block),
            "slowed_count": len(b_slow),
            # Roads a mitigation measure reopens - the visible payoff of
            # road_redundancy.
            "reopened_count": len([i for i in b_block if i not in m_set]),
            "blocked": lines(b_block),
            "slowed": lines(b_slow),
            "reopened": lines([i for i in b_block if i not in m_set]),
        }

    # ------------------------------------------------------------------
    def _footprint_lonlat(self, hazard: Any) -> dict[str, Any] | None:
        """Hazard circle as GeoJSON in lon/lat for the map."""
        try:
            geom = to_storage(hazard.footprint(), self.cfg.analysis_srid)
            ring = [[round(x, 6), round(y, 6)]
                    for x, y in geom.exterior.coords]
            return {"type": "Polygon", "coordinates": [ring]}
        except Exception:
            return None

    def _blocked_from(self, result: Any) -> tuple[list[str], list[str]]:
        for art in result.artifacts:
            if art.get("type") == "hazard":
                b = [i for i in (art.get("blocked_road_ids") or "").split(",") if i]
                s = [i for i in (art.get("slowed_road_ids") or "").split(",") if i]
                return b, s
        return [], []

    def _response_impact(
        self, base: Any, mit: Any, roads: Sequence[Any],
        lon: float, lat: float, responder_type: str,
        target_s: float, scenario_id: int | None,
    ) -> dict[str, Any]:
        """How the event — and the measures — change emergency response."""
        stations = self.repo.facilities(facility_type=responder_type)
        if not roads or not stations:
            return {"error": "insufficient data for response routing",
                    "responder_type": responder_type}

        G = build_graph(roads, mode="emergency")
        incident = self._point(lon, lat)
        prov = self._prov("network.emergency_routing",
                          {"responder_type": responder_type,
                           "response_target_seconds": target_s}, scenario_id)

        b_block, b_slow = self._blocked_from(base)
        m_block, m_slow = self._blocked_from(mit)
        Gb, _ = degrade_graph(G, blocked_road_ids=b_block, slowed_road_ids=b_slow)
        Gm, _ = degrade_graph(G, blocked_road_ids=m_block, slowed_road_ids=m_slow)

        normal = route_to_incident(G, incident, stations, prov, top_n=1,
                                   response_target_seconds=target_s)
        during = route_to_incident(Gb, incident, stations, prov, top_n=1,
                                   response_target_seconds=target_s)
        with_m = route_to_incident(Gm, incident, stations, prov, top_n=1,
                                   response_target_seconds=target_s)
        delta = compare_routes(G, Gb, incident, stations, prov,
                               response_target_seconds=target_s)

        def first(r):
            if not r.records:
                return None
            rec = dict(r.records[0])
            if rec.get("path"):
                rec["path"] = self._to_lonlat_path(rec["path"])
            return rec

        return {
            "responder_type": responder_type,
            "roads_blocked_baseline": len(b_block),
            "roads_blocked_mitigated": len(m_block),
            "normal": first(normal),
            "during_event": first(during),
            "with_measures": first(with_m),
            "impact": delta.to_dict(),
        }

    # ------------------------------------------------------------------
    @staticmethod
    def catalogue() -> dict[str, Any]:
        """Hazard types and measures, for the UI to build controls from."""
        return {
            "hazards": [
                {"id": k, "label": v["label"],
                 "defaultRadiusM": v["default_radius_m"],
                 "responderType": v["responder_type"]}
                for k, v in sorted(HAZARD_TYPES.items())
            ],
            "measures": [
                {"id": k, "label": v["label"], "reduces": v["reduces"],
                 "effect": round((1.0 - v["factor"]) * 100.0),
                 "appliesTo": list(v.get("applies_to") or []),
                 "note": v["note"]}
                for k, v in sorted(MEASURES.items())
            ],
        }