"use client";

import { useScenarioStore } from "@/stores/scenario-store";
import { useWindowStore } from "@/stores/window-store";
import NextAction from "@/components/workflow/NextAction";
import { Empty, SectionTitle } from "@/components/ui/Bits";

const ICON: Record<string, string> = { facility: "◈", road: "─", zoning: "▦", population: "▲" };

export default function ChangesPanel() {
  const { scenarios, activeId, setStatus } = useScenarioStore();
  const openWindow = useWindowStore((s) => s.openWindow);

  const active = scenarios.find((s) => s.id === activeId) ?? scenarios[0] ?? null;

  if (!active) {
    return <Empty>No active scenario selected. Open Scenario Manager to create or select a scenario.</Empty>;
  }

  const changes = active.changes || [];

  // Compute aggregate plan impact metrics from proposed changes
  const facilityCount = changes.filter((c) => c.type === "facility").length;
  const roadCount = changes.filter((c) => c.type === "road").length;
  const zoningCount = changes.filter((c) => c.type === "zoning").length;

  const estimatedCostMs = (facilityCount * 12.5 + roadCount * 8.0 + zoningCount * 2.0).toFixed(1);
  const estimatedPopServed = (facilityCount * 45000 + roadCount * 28000).toLocaleString();

  return (
    <div>
      {/* Scenario Context Banner */}
      <div
        style={{
          marginBottom: 12,
          padding: "10px 12px",
          borderRadius: "8px",
          background: "rgba(167, 139, 250, 0.08)",
          border: "1px solid rgba(167, 139, 250, 0.35)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between"
        }}
      >
        <div>
          <div style={{ fontSize: 10, fontFamily: "var(--mono)", color: "var(--violet)", fontWeight: 700 }}>
            EDITING SCENARIO
          </div>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#fff", marginTop: 2 }}>
            {active.name}
          </div>
        </div>

        <span className={"chip " + (active.status === "approved" ? "good" : "warn")}>
          {active.status.toUpperCase()}
        </span>
      </div>

      <SectionTitle>Proposed City Changes ({changes.length})</SectionTitle>

      {changes.length === 0 ? (
        <Empty>
          No proposals persisted for this scenario yet.
          <br />
          Use Planning tools to add facility candidates, arterial road proposals, or zoning interventions.
        </Empty>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 12 }}>
          {changes.map((c) => (
            <div
              key={c.id}
              className="cand"
              style={{ cursor: "default", border: "1px solid var(--line-soft)" }}
            >
              <div className="top">
                <strong style={{ fontSize: 12.5 }}>
                  <span style={{ color: "var(--violet)", marginRight: 6 }}>{ICON[c.type] ?? "◈"}</span>
                  {c.label}
                </strong>
                <span className="chip info" style={{ fontSize: 9.5 }}>{c.type}</span>
              </div>
              <div className="muted" style={{ fontSize: 11.5, marginTop: 3 }}>{c.detail}</div>
            </div>
          ))}
        </div>
      )}

      {/* Aggregate Impact Summary */}
      {changes.length > 0 && (
        <>
          <SectionTitle>Estimated Package Impact</SectionTitle>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 6,
              marginBottom: 12
            }}
          >
            <div
              style={{
                padding: "8px 10px",
                background: "rgba(0,0,0,0.25)",
                border: "1px solid var(--line-soft)",
                borderRadius: "6px"
              }}
            >
              <div className="muted" style={{ fontSize: 10 }}>Est. Capital Cost</div>
              <div className="mono" style={{ fontSize: 14, fontWeight: 700, color: "var(--warn)", marginTop: 2 }}>
                ${estimatedCostMs} M
              </div>
            </div>

            <div
              style={{
                padding: "8px 10px",
                background: "rgba(0,0,0,0.25)",
                border: "1px solid var(--line-soft)",
                borderRadius: "6px"
              }}
            >
              <div className="muted" style={{ fontSize: 10 }}>Pop. Benefiting</div>
              <div className="mono" style={{ fontSize: 14, fontWeight: 700, color: "var(--good)", marginTop: 2 }}>
                +{estimatedPopServed}
              </div>
            </div>
          </div>
        </>
      )}

      {/* Action Buttons */}
      <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
        <button
          className="btn ghost"
          style={{ flex: 1, padding: "5px", fontSize: 11 }}
          onClick={() => openWindow("analysis")}
        >
          Validate All 🗹
        </button>

        <button
          className="btn ghost"
          style={{ flex: 1, padding: "5px", fontSize: 11 }}
          onClick={() => openWindow("simulation")}
        >
          Simulate All ▶
        </button>
      </div>

      <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
        <button
          className="btn primary"
          style={{ flex: 1, padding: "6px", fontSize: 11.5, fontWeight: 600 }}
          onClick={() => openWindow("emergency")}
        >
          Stress-Test Plan ⚡
        </button>

        <button
          className="btn ghost"
          style={{ flex: 1, padding: "6px", fontSize: 11.5 }}
          onClick={async () => {
            await setStatus(active.id, active.status === "approved" ? "reopened" : "approved");
          }}
        >
          {active.status === "approved" ? "Reopen Draft" : "Commit Scenario ✓"}
        </button>
      </div>

      {/* Next Step Guidance */}
      <NextAction
        title="SCENARIO ADVANCEMENT"
        prompt={
          changes.length > 0
            ? `Scenario "${active.name}" contains ${changes.length} changes. Stress-test accessibility and disaster resilience next.`
            : "Add facility or road proposals using Planning tools, then return here to validate."
        }
        actionLabel="Stress-Test Plan"
        targetWindow="emergency"
        secondaryActionLabel="Compare with Baseline"
        secondaryTargetWindow="comparison"
        variant="primary"
      />
    </div>
  );
}
