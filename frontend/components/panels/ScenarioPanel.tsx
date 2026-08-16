"use client";
import { useState } from "react";
import { useScenarioStore } from "@/stores/scenario-store";
import { useWindowStore } from "@/stores/window-store";
import { Field, KV, SectionTitle } from "@/components/ui/Bits";

const STATUS_CHIP: Record<string, string> = { baseline: "info", draft: "warn", review: "warn", approved: "good" };

export default function ScenarioPanel() {
  const { scenarios, activeId, setActive, createScenario, setStatus, setGrowth } = useScenarioStore();
  const openWindow = useWindowStore((s) => s.openWindow);
  const [name, setName] = useState("Plan C — South ring");
  const [horizon, setHorizon] = useState(2040);
  const [growth, setG] = useState(34);
  const active = scenarios.find((s) => s.id === activeId)!;

  return (
    <div>
      <SectionTitle>Scenarios</SectionTitle>
      {scenarios.map((s) => (
        <div key={s.id} className={"cand" + (s.id === activeId ? " on" : "")} onClick={() => setActive(s.id)}>
          <div className="top">
            <strong style={{ fontSize: 12.5 }}>{s.name}</strong>
            <span className={"chip " + (STATUS_CHIP[s.status] ?? "info")}>{s.status}</span>
          </div>
          <div className="muted mono" style={{ fontSize: 10.5, marginTop: 3 }}>
            {s.id} · horizon {s.horizon} · growth +{s.populationGrowthPct}% · {s.changes.length} changes
          </div>
        </div>
      ))}

      <SectionTitle>Active scenario</SectionTitle>
      <KV k="Name" v={active.name} />
      <KV k="Created" v={active.createdAt} />
      <KV k="Changes" v={active.changes.length} />
      <div className="field" style={{ marginTop: 8 }}>
        <label>Population growth {active.populationGrowthPct}%</label>
        <input type="range" min={0} max={80} value={active.populationGrowthPct} style={{ width: "100%" }}
          onChange={(e) => setGrowth(active.id, Number(e.target.value))} />
      </div>
      <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
        <button className="btn ghost" style={{ flex: 1 }} onClick={() => openWindow("changes")}>Changes</button>
        <button className="btn ghost" style={{ flex: 1 }} onClick={() => setStatus(active.id, active.status === "approved" ? "draft" : "approved")}>
          {active.status === "approved" ? "Reopen" : "Approve"}
        </button>
        <button className="btn ghost" style={{ flex: 1 }} onClick={() => openWindow("comparison")}>Compare</button>
      </div>

      <SectionTitle>New scenario</SectionTitle>
      <Field label="Name"><input className="input" value={name} onChange={(e) => setName(e.target.value)} /></Field>
      <div style={{ display: "flex", gap: 8 }}>
        <Field label="Horizon"><input className="input" type="number" value={horizon} onChange={(e) => setHorizon(Number(e.target.value))} /></Field>
        <Field label="Growth %"><input className="input" type="number" value={growth} onChange={(e) => setG(Number(e.target.value))} /></Field>
      </div>
      <button className="btn primary wide" onClick={() => createScenario(name, horizon, growth)}>CREATE SCENARIO</button>
    </div>
  );
}
