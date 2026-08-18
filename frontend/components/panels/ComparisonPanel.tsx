"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { SectionTitle, Empty } from "@/components/ui/Bits";
import { useScenarioStore } from "@/stores/scenario-store";
import type { AnalysisResult } from "@/types";

export default function ComparisonPanel() {
  const { scenarios, activeId, setActive } = useScenarioStore();
  const [scenAId, setScenAId] = useState<string>("");
  const [scenBId, setScenBId] = useState<string>("");
  const [comparisonResult, setComparisonResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (scenarios.length >= 2) {
      if (!scenAId) setScenAId(scenarios[0].id);
      if (!scenBId) setScenBId(scenarios[1]?.id ?? scenarios[0].id);
    } else if (scenarios.length === 1) {
      if (!scenAId) setScenAId(scenarios[0].id);
      if (!scenBId) setScenBId(scenarios[0].id);
    }
  }, [scenarios, scenAId, scenBId]);

  const runComparison = async (a: string, b: string) => {
    if (!a || !b) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.compareScenarios([a, b]);
      setComparisonResult(res);
    } catch (err: any) {
      console.error("Comparison failed:", err);
      setError(err.message || "Failed to compare scenarios");
      setComparisonResult(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (scenAId && scenBId && scenAId !== scenBId) {
      runComparison(scenAId, scenBId);
    }
  }, [scenAId, scenBId]);

  const scenA = scenarios.find((s) => s.id === scenAId) ?? scenarios[0];
  const scenB = scenarios.find((s) => s.id === scenBId) ?? scenarios[1];

  const winnerEntity = comparisonResult?.entities?.[0];
  const winnerName = winnerEntity ? winnerEntity.label : (scenA?.name ?? "Scenario A");

  return (
    <div>
      <SectionTitle>Real Scenario Comparison</SectionTitle>

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <div style={{ flex: 1 }}>
          <label style={{ fontSize: 11, display: "block", marginBottom: 3 }} className="muted">Scenario A</label>
          <select className="input" value={scenAId} onChange={(e) => setScenAId(e.target.value)}>
            {scenarios.map((s) => (
              <option key={s.id} value={s.id}>{s.name} ({s.id})</option>
            ))}
          </select>
        </div>
        <div style={{ flex: 1 }}>
          <label style={{ fontSize: 11, display: "block", marginBottom: 3 }} className="muted">Scenario B</label>
          <select className="input" value={scenBId} onChange={(e) => setScenBId(e.target.value)}>
            {scenarios.map((s) => (
              <option key={s.id} value={s.id}>{s.name} ({s.id})</option>
            ))}
          </select>
        </div>
      </div>

      {loading && <Empty>Querying backend comparison engine (POST /scenarios/compare)…</Empty>}

      {error && (
        <div style={{ padding: 10, background: "rgba(239,68,68,.1)", border: "1px solid rgba(239,68,68,.3)", borderRadius: 6, marginBottom: 12, fontSize: 12, color: "var(--warn)" }}>
          Comparison failed: {error}
        </div>
      )}

      {comparisonResult && !loading && (
        <>
          <SectionTitle>{comparisonResult.title}</SectionTitle>
          <table className="grid">
            <thead>
              <tr>
                <th>Metric</th>
                <th className="num">{scenA?.name ?? "Plan A"}</th>
                <th className="num">{scenB?.name ?? "Plan B"}</th>
              </tr>
            </thead>
            <tbody>
              {comparisonResult.metrics.map((m) => (
                <tr key={m.key}>
                  <td>{m.label}</td>
                  <td className="num">{String(m.value)} {m.unit ?? ""}</td>
                  <td className="num">{String(m.value)} {m.unit ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div style={{ marginTop: 12, padding: 10, border: "1px solid rgba(52,211,153,.35)", borderRadius: 7, background: "rgba(52,211,153,.08)" }}>
            <div className="row">
              <strong style={{ letterSpacing: ".1em" }}>PROPOSED STATE → {winnerName.toUpperCase()}</strong>
              {scenAId && (
                <button className="btn ghost" style={{ padding: "3px 8px" }} onClick={() => setActive(scenAId)}>
                  Make Active
                </button>
              )}
            </div>
            <div className="muted" style={{ fontSize: 11.5, marginTop: 6, lineHeight: 1.6 }}>
              {comparisonResult.explanation}
            </div>
          </div>
        </>
      )}

      {!comparisonResult && !loading && !error && (
        <Empty>Select two distinct scenarios above to compute multi-criteria trade-offs using the backend engine.</Empty>
      )}
    </div>
  );
}
