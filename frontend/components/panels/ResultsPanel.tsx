"use client";
import { useEffect } from "react";
import { useAnalysisStore } from "@/stores/analysis-store";
import { mapBridge } from "@/cesium/map-bridge";
import { Empty, MetricCards, SectionTitle } from "@/components/ui/Bits";
import { useSelectionStore } from "@/stores/selection-store";

export default function ResultsPanel() {
  const { results, activeId, setActive } = useAnalysisStore();
  const select = useSelectionStore((s) => s.select);
  const result = results.find((r) => r.resultId === activeId) ?? results[0] ?? null;

  useEffect(() => {
    if (result?.entities?.length) {
      mapBridge.showCandidates(result.entities);
    }
  }, [result]);

  if (!result) return <Empty>No results yet. Results produced by any engine (suitability, accessibility, risk, optimisation) share this generic viewer.</Empty>;

  return (
    <div>
      <SectionTitle>Result history</SectionTitle>
      <div style={{ display: "flex", gap: 5, flexWrap: "wrap", marginBottom: 10 }}>
        {results.map((r) => (
          <button key={r.resultId} className={"chip " + (r.resultId === result.resultId ? "info" : "")} onClick={() => setActive(r.resultId)}>
            {r.type} · {new Date(r.createdAt).toLocaleTimeString()}
          </button>
        ))}
      </div>

      <MetricCards metrics={result.metrics} />

      <SectionTitle>Table</SectionTitle>
      <table className="grid">
        <thead>
          <tr><th>Rank</th><th>Entity</th><th className="num">Score</th><th>Map</th></tr>
        </thead>
        <tbody>
          {result.entities.map((e, i) => (
            <tr key={e.entityId}>
              <td className="mono">#{i + 1}</td>
              <td>{e.label}<div className="mono muted" style={{ fontSize: 10 }}>{e.entityId}</div></td>
              <td className="num" style={{ color: i === 0 ? "var(--warn)" : undefined }}>{e.score.toFixed(1)}</td>
              <td><button className="btn ghost" style={{ padding: "2px 7px", fontSize: 10.5 }} onClick={() => { select(e.entityId); mapBridge.flyTo(e.entityId); }}>Fly</button></td>
            </tr>
          ))}
        </tbody>
      </table>

      <SectionTitle>Bound map layers</SectionTitle>
      {result.layers.map((l) => (
        <div key={l.id} className="kv"><span className="k">{l.label}</span><span className="v">{l.type} · {l.id}</span></div>
      ))}

      <SectionTitle>Provenance</SectionTitle>
      <div className="kv"><span className="k">Result id</span><span className="v">{result.resultId}</span></div>
      <div className="kv"><span className="k">Dataset version</span><span className="v">{result.datasetVersion}</span></div>
      <div className="kv"><span className="k">Scenario version</span><span className="v">{result.scenarioVersion}</span></div>
      <div className="kv"><span className="k">Created</span><span className="v">{new Date(result.createdAt).toLocaleString()}</span></div>
    </div>
  );
}
