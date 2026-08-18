"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api/client";
import { DEFAULT_WEIGHTS, SUITABILITY_STAGES } from "@/lib/mock";
import { mapBridge } from "@/cesium/map-bridge";
import { useAnalysisStore } from "@/stores/analysis-store";
import { useJobStore } from "@/stores/job-store";
import { useMapStore, type DrawMode } from "@/stores/map-store";
import { useScenarioStore } from "@/stores/scenario-store";
import { useWindowStore } from "@/stores/window-store";
import { Field, SectionTitle } from "@/components/ui/Bits";
import type { SuitabilityRequest, AnalysisResult } from "@/types";

const TOOLS: { id: DrawMode; label: string }[] = [
  { id: "select", label: "SELECT" },
  { id: "road", label: "DRAW ROAD" },
  { id: "hospital", label: "PLACE HOSPITAL" },
  { id: "school", label: "PLACE SCHOOL" },
  { id: "fire", label: "PLACE FIRE ST." },
  { id: "zone", label: "DRAW ZONE" },
  { id: "measure", label: "MEASURE" }
];

export default function PlanningPanel() {
  const [tab, setTab] = useState<"suitability" | "road">("suitability");
  const [req, setReq] = useState<SuitabilityRequest>({
    facility: "Hospital", capacity: 250, minArea: 4000, maxTravelMin: 15,
    floodRule: "Exclude High", weights: { ...DEFAULT_WEIGHTS },
    maxSlope: 15, allowedZoning: [], minDistanceSameType: null,
    serviceRadius: 2000, useNetwork: true, enforceMaxTravel: false
  });
  const [advanced, setAdvanced] = useState(false);
  const [road, setRoad] = useState({ type: "Arterial", lanes: 4, speed: 50 });
  const [roadProposalResult, setRoadProposalResult] = useState<AnalysisResult | null>(null);
  const [analyzingRoad, setAnalyzingRoad] = useState(false);

  const { drawMode, setDrawMode, drawnPath } = useMapStore();
  const { startJob, jobs } = useJobStore();
  const addResult = useAnalysisStore((s) => s.addResult);
  const openWindow = useWindowStore((s) => s.openWindow);
  const { addChange, scenarios, activeId } = useScenarioStore();
  const activeScenario = scenarios.find((x) => x.id === activeId) ?? scenarios[0] ?? { id: "1", name: "Base City" };
  const busy = jobs.some((j) => j.state === "running");

  const findSites = () => {
    openWindow("jobs");
    startJob(req.facility + " site suitability", "suitability", SUITABILITY_STAGES, async () => {
      const result = await api.suitability(req, activeScenario);
      addResult(result);
      mapBridge.showCandidates(result.entities);
      openWindow("analysis");
      openWindow("results");
    });
  };

  useEffect(() => {
    if (drawnPath.length > 1) {
      const runRoadAnalysis = async () => {
        setAnalyzingRoad(true);
        try {
          const lineGeoJSON = {
            type: "LineString",
            coordinates: drawnPath.map((pt) => [pt[0], pt[1]])
          };
          const res = await api.roadProposal({
            geometry: lineGeoJSON,
            road_type: road.type,
            lanes: road.lanes,
            speed: road.speed,
            scenario_id: activeScenario.id
          });
          setRoadProposalResult(res);
        } catch (err) {
          console.error("Road analysis failed:", err);
          setRoadProposalResult(null);
        } finally {
          setAnalyzingRoad(false);
        }
      };
      runRoadAnalysis();
    } else {
      setRoadProposalResult(null);
    }
  }, [drawnPath, road.type, road.lanes, road.speed, activeScenario.id]);

  return (
    <div>
      <div className="tabs">
        <button className={"tab" + (tab === "suitability" ? " on" : "")} onClick={() => setTab("suitability")}>Site suitability</button>
        <button className={"tab" + (tab === "road" ? " on" : "")} onClick={() => setTab("road")}>Road / infrastructure</button>
      </div>

      <SectionTitle>Toolbar</SectionTitle>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginBottom: 12 }}>
        {TOOLS.map((t) => (
          <button key={t.id} className={"btn " + (drawMode === t.id ? "" : "ghost")} style={{ padding: "4px 8px", fontSize: 10.5, letterSpacing: ".06em" }}
            onClick={() => setDrawMode(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "suitability" ? (
        <>
          <Field label="Facility">
            <select className="input" value={req.facility} onChange={(e) => setReq({ ...req, facility: e.target.value as SuitabilityRequest["facility"] })}>
              {["Hospital", "School", "Fire Station", "Water Treatment"].map((f) => <option key={f}>{f}</option>)}
            </select>
          </Field>
          <div style={{ display: "flex", gap: 8 }}>
            <Field label="Capacity"><input className="input" type="number" value={req.capacity} onChange={(e) => setReq({ ...req, capacity: Number(e.target.value) })} /></Field>
            <Field label="Min land area (m²)"><input className="input" type="number" step={500} value={req.minArea} onChange={(e) => setReq({ ...req, minArea: Number(e.target.value) })} /></Field>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <Field label="Max travel (min)"><input className="input" type="number" value={req.maxTravelMin} onChange={(e) => setReq({ ...req, maxTravelMin: Number(e.target.value) })} /></Field>
            <Field label="Flood rule">
              <select className="input" value={req.floodRule} onChange={(e) => setReq({ ...req, floodRule: e.target.value as SuitabilityRequest["floodRule"] })}>
                {["Exclude High", "Exclude High + Medium", "Allow all"].map((f) => <option key={f}>{f}</option>)}
              </select>
            </Field>
          </div>

          <SectionTitle>Criteria weights</SectionTitle>
          {Object.keys(req.weights).map((k) => (
            <div key={k} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
              <span style={{ flex: 1, fontSize: 11.5 }}>{k}</span>
              <input type="range" min={0} max={50} value={req.weights[k]} style={{ width: 110 }}
                onChange={(e) => setReq({ ...req, weights: { ...req.weights, [k]: Number(e.target.value) } })} />
              <span className="mono" style={{ width: 32, textAlign: "right", fontSize: 11 }}>{req.weights[k]}%</span>
            </div>
          ))}
          <div className="row" style={{ margin: "6px 0 12px" }}>
            <span className="muted" style={{ fontSize: 11 }}>Total</span>
            <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <button className="btn ghost" style={{ padding: "2px 7px", fontSize: 10 }}
                title="Rescale all weights so they sum to 100"
                onClick={() => {
                  const t = Object.values(req.weights).reduce((a, b) => a + b, 0);
                  if (!t) return;
                  const w: Record<string, number> = {};
                  for (const k of Object.keys(req.weights)) w[k] = Math.round((req.weights[k] / t) * 100);
                  setReq({ ...req, weights: w });
                }}>NORMALIZE</button>
              <span className="mono" style={{ color: Object.values(req.weights).reduce((a, b) => a + b, 0) === 100 ? "var(--good)" : "var(--warn)" }}>
                {Object.values(req.weights).reduce((a, b) => a + b, 0)}%
              </span>
            </span>
          </div>

          <SectionTitle>
            <span style={{ cursor: "pointer" }} onClick={() => setAdvanced(!advanced)}>
              {advanced ? "\u25be" : "\u25b8"} Site rules (advanced)
            </span>
          </SectionTitle>
          {advanced && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ display: "flex", gap: 8 }}>
                <Field label="Max slope (deg)">
                  <input className="input" type="number" step={1} min={0} max={90}
                    value={req.maxSlope ?? ""} placeholder="any"
                    onChange={(e) => setReq({ ...req, maxSlope: e.target.value === "" ? null : Number(e.target.value) })} />
                </Field>
                <Field label="Catchment radius (m)">
                  <input className="input" type="number" step={250} min={100}
                    value={req.serviceRadius ?? 2000}
                    onChange={(e) => setReq({ ...req, serviceRadius: Number(e.target.value) })} />
                </Field>
              </div>
              <Field label="Min distance to same facility type (m)">
                <input className="input" type="number" step={250} min={0}
                  value={req.minDistanceSameType ?? ""} placeholder="no minimum"
                  onChange={(e) => setReq({ ...req, minDistanceSameType: e.target.value === "" ? null : Number(e.target.value) })} />
              </Field>
              <Field label="Allowed zoning (comma separated, blank = any)">
                <input className="input" type="text" placeholder="R1, C1, PS"
                  value={(req.allowedZoning ?? []).join(", ")}
                  onChange={(e) => setReq({ ...req, allowedZoning: e.target.value.split(",").map((z) => z.trim()).filter(Boolean) })} />
              </Field>
            </div>
          )}

          <button className="btn primary wide" disabled={busy} onClick={findSites}>{busy ? "RUNNING…" : "FIND SITES"}</button>
        </>
      ) : (
        <>
          <div style={{ display: "flex", gap: 8 }}>
            <Field label="Road type">
              <select className="input" value={road.type} onChange={(e) => setRoad({ ...road, type: e.target.value })}>
                {["Arterial", "Sub-arterial", "Collector", "Local"].map((t) => <option key={t}>{t}</option>)}
              </select>
            </Field>
            <Field label="Lanes"><input className="input" type="number" value={road.lanes} onChange={(e) => setRoad({ ...road, lanes: Number(e.target.value) })} /></Field>
            <Field label="Speed"><input className="input" type="number" value={road.speed} onChange={(e) => setRoad({ ...road, speed: Number(e.target.value) })} /></Field>
          </div>

          <button className={"btn wide " + (drawMode === "road" ? "primary" : "")} onClick={() => setDrawMode(drawMode === "road" ? "select" : "road")}>
            {drawMode === "road" ? "DRAWING… CLICK ON THE MAP" : "DRAW ALIGNMENT"}
          </button>

          {analyzingRoad && (
            <div className="muted" style={{ fontSize: 11, margin: "10px 0" }}>Running backend GIS spatial intersection analysis (POST /planning/road)…</div>
          )}

          {roadProposalResult && !analyzingRoad && (
            <>
              <SectionTitle>{roadProposalResult.title}</SectionTitle>
              {roadProposalResult.metrics.map((m) => (
                <div key={m.key} className="kv">
                  <span className="k">{m.label}</span>
                  <span className="v" style={{ color: m.better === "up" ? "var(--good)" : undefined }}>{String(m.value)}</span>
                </div>
              ))}

              <div style={{ fontSize: 11, margin: "8px 0", lineHeight: 1.5 }} className="muted">
                {roadProposalResult.explanation}
              </div>

              <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
                <button className="btn primary" style={{ flex: 1 }}
                  onClick={async () => {
                    await addChange({
                      type: "road",
                      label: roadProposalResult.title,
                      detail: `${road.lanes} lanes · ${road.speed} km/h`,
                      parameters: {
                        geometry: roadProposalResult.geometry,
                        road_type: road.type,
                        lanes: road.lanes,
                        speed: road.speed,
                        result_id: roadProposalResult.resultId
                      }
                    });
                    openWindow("changes");
                    setDrawMode("select");
                  }}>
                  ADD TO {activeScenario.name.toUpperCase()}
                </button>
                <button className="btn ghost" onClick={() => { mapBridge.clearProposals(); useMapStore.getState().setDrawnPath([]); setRoadProposalResult(null); }}>Clear</button>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
