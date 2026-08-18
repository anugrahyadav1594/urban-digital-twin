"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { useMapStore } from "@/stores/map-store";
import { useScenarioStore } from "@/stores/scenario-store";
import { useAnalysisStore } from "@/stores/analysis-store";
import { useWindowStore } from "@/stores/window-store";
import { SectionTitle, MetricCards, Field } from "@/components/ui/Bits";
import type { AnalysisResult } from "@/types";

export default function SimulationPanel() {
  const { year, setYear, playing, setPlaying } = useMapStore();
  const { scenarios, activeId } = useScenarioStore();
  const activeScenario = scenarios.find((x) => x.id === activeId) ?? scenarios[0] ?? { id: "1", name: "Base City" };
  const addResult = useAnalysisStore((s) => s.addResult);
  const openWindow = useWindowStore((s) => s.openWindow);

  const [simType, setSimType] = useState<"population" | "flood">("population");
  const [floodLevel, setFloodLevel] = useState(1.5);
  const [returnPeriod, setReturnPeriod] = useState(50);
  const [popRate, setPopRate] = useState(0.025);
  const [simResult, setSimResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => {
      const y = useMapStore.getState().year;
      if (y >= 2040) { useMapStore.getState().setPlaying(false); return; }
      useMapStore.getState().setYear(y + 1);
    }, 550);
    return () => clearInterval(t);
  }, [playing]);

  const [error, setError] = useState<string | null>(null);

  const runPopulationSim = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.simulationPopulation(2025, year, popRate);
      if (res) {
        setSimResult(res);
        addResult(res);
      } else {
        throw new Error("Population simulation returned no data from backend.");
      }
    } catch (err: any) {
      console.error("Population simulation error:", err);
      setError(err?.message || "Population simulation failed on backend.");
      setSimResult(null);
    } finally {
      setLoading(false);
    }
  };

  const runFloodSim = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.simulationFlood(floodLevel, returnPeriod);
      if (res) {
        setSimResult(res);
        addResult(res);
      } else {
        throw new Error("Flood exposure simulation returned no data from backend.");
      }
    } catch (err: any) {
      console.error("Flood simulation error:", err);
      setError(err?.message || "Flood exposure simulation failed on backend.");
      setSimResult(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="tabs" style={{ marginBottom: 12 }}>
        <button className={"tab" + (simType === "population" ? " on" : "")} onClick={() => setSimType("population")}>
          Population Projection
        </button>
        <button className={"tab" + (simType === "flood" ? " on" : "")} onClick={() => setSimType("flood")}>
          Flood Exposure
        </button>
      </div>

      {simType === "population" ? (
        <>
          <div className="row" style={{ marginBottom: 10 }}>
            <div style={{ display: "flex", gap: 6 }}>
              <button className="btn primary" style={{ width: 46 }} onClick={() => setPlaying(!playing)}>{playing ? "❚❚" : "▶"}</button>
              <button className="btn ghost" onClick={() => { setPlaying(false); setYear(2026); }}>Reset</button>
            </div>
            <div className="mono" style={{ fontSize: 22 }}>{year}</div>
          </div>

          <input type="range" min={2026} max={2040} value={year} style={{ width: "100%" }} onChange={(e) => setYear(Number(e.target.value))} />
          <div className="row mono muted" style={{ fontSize: 10, marginTop: 2, marginBottom: 12 }}>
            <span>2026</span><span>2033</span><span>2040</span>
          </div>

          <Field label="Annual growth rate">
            <input className="input" type="number" step={0.005} value={popRate} onChange={(e) => setPopRate(Number(e.target.value))} />
          </Field>

          <button className="btn primary wide" disabled={loading} onClick={runPopulationSim}>
            {loading ? "SIMULATING…" : `RUN POPULATION PROJECTION (${year})`}
          </button>
        </>
      ) : (
        <>
          <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
            <Field label="Flood depth level (m)">
              <input className="input" type="number" step={0.5} min={0.5} max={10} value={floodLevel} onChange={(e) => setFloodLevel(Number(e.target.value))} />
            </Field>
            <Field label="Return period (yrs)">
              <input className="input" type="number" step={10} min={10} max={500} value={returnPeriod} onChange={(e) => setReturnPeriod(Number(e.target.value))} />
            </Field>
          </div>

          <button className="btn primary wide" disabled={loading} onClick={runFloodSim}>
            {loading ? "ANALYZING…" : "RUN FLOOD EXPOSURE SCREEN"}
          </button>
        </>
      )}

      {error && (
        <div style={{ marginTop: 12, padding: 10, background: "rgba(239,68,68,.1)", border: "1px solid rgba(239,68,68,.3)", borderRadius: 6, fontSize: 12, color: "var(--warn)" }}>
          Simulation Error: {error}
        </div>
      )}

      {simResult && !loading && (
        <div style={{ marginTop: 12 }}>
          <SectionTitle>{simResult.title}</SectionTitle>
          <MetricCards metrics={simResult.metrics} />
          <div style={{ fontSize: 11.5, marginTop: 8, lineHeight: 1.5 }} className="muted">
            {simResult.explanation}
          </div>
          <button className="btn ghost wide" style={{ marginTop: 8 }} onClick={() => openWindow("results")}>
            Open in Results Panel
          </button>
        </div>
      )}
    </div>
  );
}
