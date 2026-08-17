"use client";
import { useState } from "react";
import { api } from "@/lib/api/client";
import { SUITABILITY_STAGES } from "@/lib/mock";
import { mapBridge } from "@/cesium/map-bridge";
import { useAnalysisStore } from "@/stores/analysis-store";
import { useJobStore } from "@/stores/job-store";
import { useScenarioStore } from "@/stores/scenario-store";
import { useSelectionStore } from "@/stores/selection-store";
import { useWindowStore } from "@/stores/window-store";
import { Bar, Empty, MetricCards, SectionTitle } from "@/components/ui/Bits";
import type { JobStage } from "@/types";

const ACCESS_STAGES: JobStage[] = [
  { key: "graph", label: "Building network graph", state: "pending" },
  { key: "iso", label: "Isochrone computation", state: "pending" },
  { key: "agg", label: "Population aggregation", state: "pending" },
  { key: "val", label: "Validation", state: "pending" }
];
const RISK_STAGES: JobStage[] = [
  { key: "dem", label: "Terrain / DEM sampling", state: "pending" },
  { key: "hyd", label: "Hydrological overlay", state: "pending" },
  { key: "exp", label: "Exposure aggregation", state: "pending" }
];

export default function AnalysisPanel() {
  const { results, activeId, setActive } = useAnalysisStore();
  const addResult = useAnalysisStore((s) => s.addResult);
  const { startJob, jobs } = useJobStore();
  const openWindow = useWindowStore((s) => s.openWindow);
  const select = useSelectionStore((s) => s.select);
  const scenario = useScenarioStore((s) => s.scenarios.find((x) => x.id === s.activeId)!);
  const [sel, setSel] = useState<string | null>(null);
  const busy = jobs.some((j) => j.state === "running");
  const result = results.find((r) => r.resultId === activeId) ?? results[0] ?? null;

  const run = (kind: "accessibility" | "risk" | "suitability") => {
    openWindow("jobs");
    const stages = kind === "accessibility" ? ACCESS_STAGES : kind === "risk" ? RISK_STAGES : SUITABILITY_STAGES;
    const title = kind === "accessibility" ? "Emergency accessibility" : kind === "risk" ? "Flood risk exposure" : "Site suitability";
    startJob(title, kind, stages, async () => {
      const r = kind === "accessibility" ? await api.accessibility(scenario) : await api.risk(scenario);
      addResult(r);
      mapBridge.showCandidates(r.entities);
    });
  };

  return (
    <div>
      <div style={{ display: "flex", gap: 6, marginBottom: 10, flexWrap: "wrap" }}>
        <button className="btn ghost" disabled={busy} onClick={() => run("accessibility")}>Accessibility</button>
        <button className="btn ghost" disabled={busy} onClick={() => run("risk")}>Flood risk</button>
        <button className="btn ghost" onClick={() => openWindow("planning")}>Site suitability…</button>
        <button className="btn ghost" onClick={() => { mapBridge.clearCandidates(); }}>Clear map</button>
      </div>

      {results.length > 1 && (
        <div style={{ display: "flex", gap: 5, marginBottom: 10, flexWrap: "wrap" }}>
          {results.map((r) => (
            <button key={r.resultId} className={"chip " + (r.resultId === (result?.resultId ?? "") ? "info" : "")} onClick={() => setActive(r.resultId)}>
              {r.type}
            </button>
          ))}
        </div>
      )}

      {!result ? (
        <Empty>Run an analysis to see metrics, ranked entities and map bindings.<br /><span className="mono" style={{ fontSize: 11 }}>POST /analysis/* → job_id → result_id</span></Empty>
      ) : (
        <>
          <div className="row" style={{ marginBottom: 8 }}>
            <strong>{result.title}</strong>
            <span className="mono muted" style={{ fontSize: 10.5 }}>{result.resultId}</span>
          </div>
          <MetricCards metrics={result.metrics} />

          <SectionTitle>Ranked entities</SectionTitle>
          {result.entities.length === 0 && <Empty>No entity satisfies the constraints.</Empty>}
          {result.entities.map((e, i) => (
            <div key={e.entityId} className={"cand" + (sel === e.entityId ? " on" : "")}
              onClick={() => { setSel(e.entityId); select(e.entityId); mapBridge.flyTo(e.entityId); }}>
              <div className="top">
                <span><span className="rank">#{i + 1}</span> &nbsp;{e.label}</span>
                <span className="score">{e.score.toFixed(1)}</span>
              </div>
              <div style={{ marginTop: 5 }}><Bar value={e.score} /></div>
              {sel === e.entityId && (
                <div style={{ marginTop: 8 }}>
                  {Object.entries(e.breakdown).map(([k, v]) => (
                    <div key={k} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3 }}>
                      <span style={{ flex: 1, fontSize: 11 }} className="muted">{k}</span>
                      <div style={{ width: 90 }}><Bar value={Number(v)} /></div>
                      <span className="mono" style={{ fontSize: 10.5, width: 26, textAlign: "right" }}>{Math.round(Number(v))}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}

          <SectionTitle>Explanation</SectionTitle>
          <div style={{ fontSize: 12, lineHeight: 1.6 }} className="muted">{result.explanation}</div>

          <div className="hr" />
          <div className="row">
            <span className="mono muted" style={{ fontSize: 10 }}>{result.datasetVersion} · {result.scenarioVersion}</span>
            <button className="btn ghost" style={{ padding: "3px 8px" }} onClick={() => openWindow("results")}>Open results</button>
          </div>
        </>
      )}
    </div>
  );
}
