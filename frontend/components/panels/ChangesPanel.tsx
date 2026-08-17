"use client";
import { useScenarioStore } from "@/stores/scenario-store";
import { Empty, SectionTitle } from "@/components/ui/Bits";

const ICON: Record<string, string> = { facility: "◈", road: "─", zoning: "▦", population: "▲" };

export default function ChangesPanel() {
  const { scenarios, activeId } = useScenarioStore();
  const active = scenarios.find((s) => s.id === activeId)!;

  return (
    <div>
      <SectionTitle>{active.name} · change set</SectionTitle>
      {active.changes.length === 0 && <Empty>No changes yet. Use Planning tools to add facilities, roads or rezoning proposals.</Empty>}
      {active.changes.map((c) => (
        <div key={c.id} className="cand" style={{ cursor: "default" }}>
          <div className="top">
            <strong style={{ fontSize: 12.5 }}><span style={{ color: "var(--violet)", marginRight: 6 }}>{ICON[c.type]}</span>{c.label}</strong>
            <span className="chip">{c.type}</span>
          </div>
          <div className="muted" style={{ fontSize: 11.5, marginTop: 3 }}>{c.detail}</div>
        </div>
      ))}
    </div>
  );
}
