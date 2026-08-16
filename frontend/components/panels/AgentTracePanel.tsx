"use client";
import { useAIStore } from "@/stores/ai-store";
import { Empty, SectionTitle } from "@/components/ui/Bits";

export default function AgentTracePanel() {
  const { steps, thinking } = useAIStore();
  if (steps.length === 0) return <Empty>Agent trace is empty. Ask the Planning Assistant a question to see which deterministic tool each agent calls.</Empty>;

  return (
    <div>
      <SectionTitle>Orchestration trace {thinking && <span className="spin" style={{ marginLeft: 6 }}>●</span>}</SectionTitle>
      {steps.map((s) => (
        <div key={s.id} className="trace-step">
          <span className="mark" style={{ color: s.state === "done" ? "var(--good)" : "var(--accent)", width: 14 }}>
            {s.state === "done" ? "✓" : <span className="spin">●</span>}
          </span>
          <span className="agent">{s.agent}</span>
          <span style={{ flex: 1 }}>
            {s.text}
            {s.tool && <div className="mono muted" style={{ fontSize: 10, marginTop: 2 }}>tool: {s.tool}()</div>}
          </span>
        </div>
      ))}
      <div className="hr" />
      <div className="muted" style={{ fontSize: 11, lineHeight: 1.6 }}>
        The LLM only orchestrates and explains. Every quantitative value is produced by a deterministic engine
        (GIS, network, risk, optimisation) and carries a result id and dataset version.
      </div>
    </div>
  );
}
