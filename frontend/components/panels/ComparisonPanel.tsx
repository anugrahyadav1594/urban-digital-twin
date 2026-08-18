"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { SectionTitle, Empty } from "@/components/ui/Bits";
import { useScenarioStore } from "@/stores/scenario-store";
import type { AnalysisResult, ComparedScenario } from "@/types";

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
    if (a === b) {
      setError("Please select two distinct scenarios to compare.");
      setComparisonResult(null);
      return;
    }
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

  const comparedList = comparisonResult?.scenarios || [];
  const recA = comparedList.find((s) => String(s.scenarioId) === String(scenAId)) || comparedList[0];
  const recB = comparedList.find((s) => String(s.scenarioId) === String(scenBId)) || comparedList[1];
  const bestScen = comparedList.find((s) => s.rank === 1) || recA;

  // Extract all unique metric keys
  const metricKeys = Array.from(new Set([
    ...Object.keys(recA?.metrics || {}),
    ...Object.keys(recB?.metrics || {})
  ]));

  const formatMetricName = (key: string) => {
    return key.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
  };

  const formatValue = (val: number | null | undefined) => {
    if (val === null || val === undefined) return "—";
    if (Math.abs(val) >= 1000) return val.toLocaleString();
    if (Number.isInteger(val)) return String(val);
    return val.toFixed(2);
  };

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

      {loading && <Empty>Computing trade-off matrix on backend (POST /scenarios/compare)…</Empty>}

      {error && (
        <div style={{ padding: 10, background: "rgba(239,68,68,.1)", border: "1px solid rgba(239,68,68,.3)", borderRadius: 6, marginBottom: 12, fontSize: 12, color: "var(--warn)" }}>
          Comparison warning: {error}
        </div>
      )}

      {comparisonResult && !loading && (
        <>
          <SectionTitle>{comparisonResult.title}</SectionTitle>
          <table className="grid">
            <thead>
              <tr>
                <th>Metric</th>
                <th className="num">{recA?.name || scenA?.name || "Scenario A"}</th>
                <th className="num">{recB?.name || scenB?.name || "Scenario B"}</th>
              </tr>
            </thead>
            <tbody>
              {metricKeys.length === 0 && (
                <tr><td colSpan={3} style={{ textAlign: "center" }} className="muted">No metrics to display</td></tr>
              )}
              {metricKeys.map((key) => {
                const valA = recA?.metrics?.[key];
                const valB = recB?.metrics?.[key];
                const aWins = (valA ?? 0) > (valB ?? 0);
                const bWins = (valB ?? 0) > (valA ?? 0);
                return (
                  <tr key={key}>
                    <td>{formatMetricName(key)}</td>
                    <td className="num" style={{ color: aWins ? "var(--good)" : undefined }}>
                      {formatValue(valA)}
                    </td>
                    <td className="num" style={{ color: bWins ? "var(--good)" : undefined }}>
                      {formatValue(valB)}
                    </td>
                  </tr>
                );
              })}
              {recA && recB && (
                <tr className="win">
                  <td><strong>Overall Engine Score</strong></td>
                  <td className="num"><strong>{(recA.score * 100).toFixed(1)}%</strong></td>
                  <td className="num"><strong>{(recB.score * 100).toFixed(1)}%</strong></td>
                </tr>
              )}
            </tbody>
          </table>

          <div style={{ marginTop: 12, padding: 10, border: "1px solid rgba(52,211,153,.35)", borderRadius: 7, background: "rgba(52,211,153,.08)" }}>
            <div className="row">
              <strong style={{ letterSpacing: ".1em" }}>RECOMMENDED → {(bestScen?.name || "SCENARIO A").toUpperCase()}</strong>
              {bestScen?.scenarioId && (
                <button className="btn ghost" style={{ padding: "3px 8px" }} onClick={() => setActive(bestScen.scenarioId)}>
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
        <Empty>Select two distinct scenarios above to compute trade-offs on the backend.</Empty>
      )}
    </div>
  );
}
