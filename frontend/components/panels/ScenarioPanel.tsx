"use client";
import { useEffect, useState } from "react";
import { useScenarioStore } from "@/stores/scenario-store";
import { useWindowStore } from "@/stores/window-store";
import { Field, KV, SectionTitle } from "@/components/ui/Bits";

const STATUS_CHIP: Record<string, string> = {
  baseline: "info",
  draft: "warn",
  review: "warn",
  approved: "good",
  reopened: "warn"
};

export default function ScenarioPanel() {
  const { scenarios, activeId, setActive, loadScenarios, createScenario, setStatus, setGrowth, loading } = useScenarioStore();
  const openWindow = useWindowStore((s) => s.openWindow);
  const [name, setName] = useState("Plan C — South ring");
  const [horizon, setHorizon] = useState(2040);
  const [growth, setG] = useState(3.4);
  const [desc, setDesc] = useState("Regional transit corridor and facility expansion");

  useEffect(() => {
    loadScenarios();
  }, [loadScenarios]);

  const active = scenarios.find((s) => s.id === activeId) ?? scenarios[0] ?? null;

  return (
    <div>
      <SectionTitle>Scenarios {loading && <span style={{ fontSize: 10, color: "var(--accent)" }}>loading…</span>}</SectionTitle>
      {scenarios.length === 0 && !loading && (
        <div className="muted" style={{ fontSize: 11, padding: 8 }}>No scenarios found in database.</div>
      )}
      {scenarios.map((s) => (
        <div key={s.id} className={"cand" + (s.id === activeId ? " on" : "")} onClick={() => setActive(s.id)}>
          <div className="top">
            <strong style={{ fontSize: 12.5 }}>{s.name}</strong>
            <span className={"chip " + (STATUS_CHIP[s.status] ?? "info")}>{s.status}</span>
          </div>
          <div className="muted mono" style={{ fontSize: 10.5, marginTop: 3 }}>
            ID: {s.id} · horizon {s.horizon} · growth +{s.populationGrowthPct}% · {s.changes?.length ?? 0} changes
          </div>
        </div>
      ))}

      {active && (
        <>
          <SectionTitle>Active scenario</SectionTitle>
          <KV k="Name" v={active.name} />
          <KV k="Status" v={active.status} />
          <KV k="Created" v={active.createdAt ? active.createdAt.slice(0, 10) : "N/A"} />
          <KV k="Changes" v={active.changes?.length ?? 0} />
          <div className="field" style={{ marginTop: 8 }}>
            <label>Population growth {active.populationGrowthPct}%</label>
            <input
              type="range"
              min={0}
              max={20}
              step={0.1}
              value={active.populationGrowthPct}
              style={{ width: "100%" }}
              onChange={(e) => setGrowth(active.id, Number(e.target.value))}
            />
          </div>
          <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
            <button className="btn ghost" style={{ flex: 1 }} onClick={() => openWindow("changes")}>Changes</button>
            <button
              className="btn ghost"
              style={{ flex: 1 }}
              onClick={() => setStatus(active.id, active.status === "approved" ? "reopened" : "approved")}
            >
              {active.status === "approved" ? "Reopen" : "Approve"}
            </button>
            <button className="btn ghost" style={{ flex: 1 }} onClick={() => openWindow("comparison")}>Compare</button>
          </div>
        </>
      )}

      <SectionTitle>New scenario</SectionTitle>
      <Field label="Name"><input className="input" value={name} onChange={(e) => setName(e.target.value)} /></Field>
      <Field label="Description"><input className="input" value={desc} onChange={(e) => setDesc(e.target.value)} /></Field>
      <div style={{ display: "flex", gap: 8 }}>
        <Field label="Horizon"><input className="input" type="number" value={horizon} onChange={(e) => setHorizon(Number(e.target.value))} /></Field>
        <Field label="Growth %"><input className="input" type="number" step={0.1} value={growth} onChange={(e) => setG(Number(e.target.value))} /></Field>
      </div>
      <button
        className="btn primary wide"
        disabled={loading || !name}
        onClick={async () => {
          await createScenario(name, horizon, growth, desc);
        }}
      >
        CREATE SCENARIO
      </button>
    </div>
  );
}
