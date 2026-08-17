"use client";
import { useState } from "react";
import { api } from "@/lib/api/client";
import { DEFAULT_WEIGHTS, SUITABILITY_STAGES } from "@/lib/mock";
import { mapBridge } from "@/cesium/map-bridge";
import { useAnalysisStore } from "@/stores/analysis-store";
import { useJobStore } from "@/stores/job-store";
import { useMapStore, type DrawMode } from "@/stores/map-store";
import { useScenarioStore } from "@/stores/scenario-store";
import { useWindowStore } from "@/stores/window-store";
import { Field, SectionTitle } from "@/components/ui/Bits";
import type { SuitabilityRequest } from "@/types";

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
    floodRule: "Exclude High", weights: { ...DEFAULT_WEIGHTS }
  });
  const [road, setRoad] = useState({ type: "Arterial", lanes: 4, speed: 50 });

  const { drawMode, setDrawMode, drawnPath } = useMapStore();
  const { startJob, jobs } = useJobStore();
  const addResult = useAnalysisStore((s) => s.addResult);
  const openWindow = useWindowStore((s) => s.openWindow);
  const { addChange } = useScenarioStore();
  const activeScenario = useScenarioStore((s) => s.scenarios.find((x) => x.id === s.activeId)!);
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

  const roadLengthKm = drawnPath.length > 1
    ? drawnPath.slice(1).reduce((s, p, i) => s + Math.hypot((p[0] - drawnPath[i][0]) * 105.6, (p[1] - drawnPath[i][1]) * 111), 0)
    : 0;

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
            <span className="mono" style={{ color: Object.values(req.weights).reduce((a, b) => a + b, 0) === 100 ? "var(--good)" : "var(--warn)" }}>
              {Object.values(req.weights).reduce((a, b) => a + b, 0)}%
            </span>
          </div>

          <button className="btn primary wide" disabled={busy} onClick={findSites}>{busy ? "RUNNING…" : "FIND SITES"}</button>
          <div className="muted" style={{ fontSize: 10.5, marginTop: 6, textAlign: "center" }}>
            POST /planning/suitability → job → result → map highlight
          </div>
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

          {drawnPath.length > 1 && (
            <>
              <SectionTitle>Road proposal</SectionTitle>
              <div className="kv"><span className="k">Length</span><span className="v">{roadLengthKm.toFixed(2)} km</span></div>
              <div className="kv"><span className="k">Affected parcels</span><span className="v">{Math.round(roadLengthKm * 9)}</span></div>
              <div className="kv"><span className="k">Affected buildings</span><span className="v">{Math.round(roadLengthKm * 2.8)}</span></div>
              <div className="kv"><span className="k">Connectivity impact</span><span className="v" style={{ color: "var(--good)" }}>+{Math.round(roadLengthKm * 4.3)}%</span></div>
              <div className="kv"><span className="k">Avg travel time</span><span className="v" style={{ color: "var(--good)" }}>-{Math.round(roadLengthKm * 3.3)}%</span></div>
              <div className="kv"><span className="k">Emergency access</span><span className="v" style={{ color: "var(--good)" }}>+{Math.round(roadLengthKm * 5.2)}%</span></div>
              <div className="kv"><span className="k">Flood exposure</span><span className="v">Low</span></div>
              <div className="kv"><span className="k">Indicative cost</span><span className="v">₹{Math.round(roadLengthKm * 9.6)} Cr</span></div>

              <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
                <button className="btn primary" style={{ flex: 1 }}
                  onClick={() => {
                    addChange({ type: "road", label: road.type + " link " + roadLengthKm.toFixed(1) + " km", detail: road.lanes + " lanes · " + road.speed + " km/h" });
                    openWindow("changes");
                    setDrawMode("select");
                  }}>
                  ADD TO {activeScenario.name.toUpperCase()}
                </button>
                <button className="btn ghost" onClick={() => { mapBridge.clearProposals(); useMapStore.getState().setDrawnPath([]); }}>Clear</button>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
