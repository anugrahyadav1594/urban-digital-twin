"use client";

import { useEffect } from "react";
import { useAnalysisStore } from "@/stores/analysis-store";
import { mapBridge } from "@/cesium/map-bridge";
import { Empty, MetricCards, SectionTitle } from "@/components/ui/Bits";
import { useSelectionStore } from "@/stores/selection-store";
import { useWindowStore } from "@/stores/window-store";
import { useScenarioStore } from "@/stores/scenario-store";
import { useWorkflowStore } from "@/stores/workflow-store";
import NextAction from "@/components/workflow/NextAction";
import type { ResultEntity } from "@/types";

export default function ResultsPanel() {
  const { results, activeId, setActive } = useAnalysisStore();
  const select = useSelectionStore((s) => s.select);
  const openWindow = useWindowStore((s) => s.openWindow);
  const { addChange, activeId: activeScenarioId, scenarios } = useScenarioStore();
  const { advanceStep, currentWorkflow, currentStep } = useWorkflowStore();

  const activeScenario = scenarios.find((s) => s.id === activeScenarioId) ?? scenarios[0];

  const result =
    results.find((r) => r.resultId === activeId) ??
    results[0] ??
    null;

  useEffect(() => {
    if (result?.entities?.length) {
      mapBridge.showCandidates(result.entities);
    }
  }, [result]);

  if (!result) {
    return (
      <div>
        <Empty>
          No analysis results available yet. Run a site suitability, accessibility, road proposal, or disaster simulation to inspect ranked outputs.
        </Empty>

        <NextAction
          title="NEXT DECISION"
          prompt="Start by defining a facility requirement or searching candidate sites."
          actionLabel="Open Planning Tools"
          targetWindow="planning"
          autoAdvanceWorkflow={false}
        />
      </div>
    );
  }

  const topEntity = result.entities?.[0] ?? null;

  const flyToResult = (entity: ResultEntity) => {
    if (!entity?.entityId) return;
    select(entity.entityId);
    mapBridge.flyTo(entity.entityId);
  };

  const inspectResult = (entity: ResultEntity) => {
    if (!entity?.entityId) return;
    select(entity.entityId);
    mapBridge.flyTo(entity.entityId);
    openWindow("inspector");
  };

  const handleAddToScenario = async (entity: ResultEntity) => {
    await addChange({
      type: "facility",
      label: `Candidate ${entity.label}`,
      detail: `${entity.score != null ? `Suitability score ${entity.score.toFixed(1)}/100` : entity.label} · ${result.title}`,
      object_id: Number(entity.entityId.replace(/[^0-9]/g, "")) || undefined,
      parameters: {
        score: entity.score,
        position: entity.position,
        breakdown: entity.breakdown,
        result_id: result.resultId
      }
    });
    openWindow("changes");
  };

  return (
    <div>
      {/* Result History Chips */}
      <div className="row" style={{ marginBottom: 8 }}>
        <SectionTitle style={{ margin: 0 }}>Result history</SectionTitle>
        <span className="mono muted" style={{ fontSize: 10.5 }}>
          {results.length} run(s)
        </span>
      </div>

      <div
        style={{
          display: "flex",
          gap: 5,
          flexWrap: "wrap",
          marginBottom: 12
        }}
      >
        {results.map((r) => (
          <button
            key={r.resultId}
            className={
              "chip " +
              (r.resultId === result.resultId ? "info" : "")
            }
            onClick={() => setActive(r.resultId)}
          >
            {r.type} · {new Date(r.createdAt).toLocaleTimeString()}
          </button>
        ))}
      </div>

      {/* Recommended Option Feature Box */}
      {topEntity && (
        <div
          style={{
            marginBottom: 12,
            padding: "11px 12px",
            borderRadius: "8px",
            background: "linear-gradient(135deg, rgba(56,189,248,0.12), rgba(34,211,238,0.04))",
            border: "1.5px solid rgba(56,189,248,0.4)",
            boxShadow: "0 6px 18px rgba(0,0,0,0.3)"
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
            <span
              style={{
                fontSize: 10,
                fontFamily: "var(--mono)",
                fontWeight: 700,
                letterSpacing: ".12em",
                color: "var(--accent)",
                textTransform: "uppercase"
              }}
            >
              ★ RECOMMENDED OPTION
            </span>
            <span className="chip good" style={{ fontSize: 10 }}>
              {topEntity.score != null
                ? `Score: ${topEntity.score.toFixed(1)} / 100`
                : topEntity.metrics?.coverage_ratio != null
                ? `Coverage: ${(Number(topEntity.metrics.coverage_ratio) * 100).toFixed(1)}%`
                : "Optimized Site"}
            </span>
          </div>

          <div style={{ fontSize: 13.5, fontWeight: 700, color: "#fff", marginBottom: 4 }}>
            {topEntity.label}
          </div>

          <div style={{ fontSize: 11.5, color: "var(--txt-dim)", lineHeight: 1.5, marginBottom: 8 }}>
            Why recommended: Top suitability score based on network connectivity, travel time targets, and environmental constraint exclusions.
          </div>

          <div style={{ display: "flex", gap: 6 }}>
            <button
              className="btn primary"
              style={{ flex: 1, padding: "4px 8px", fontSize: 11 }}
              onClick={() => inspectResult(topEntity)}
            >
              Inspect in 3D ⊙
            </button>

            <button
              className="btn ghost"
              style={{ flex: 1, padding: "4px 8px", fontSize: 11 }}
              onClick={() => handleAddToScenario(topEntity)}
            >
              Add to {activeScenario?.name ?? "Scenario"} +
            </button>
          </div>
        </div>
      )}

      {/* Metric Cards */}
      <MetricCards metrics={result.metrics} />

      {/* Decision-Oriented Ranked Table */}
      <SectionTitle>Ranked Alternatives</SectionTitle>

      <table className="grid">
        <thead>
          <tr>
            <th>Rank</th>
            <th>Entity</th>
            <th className="num">Score</th>
            <th style={{ textAlign: "right" }}>Actions</th>
          </tr>
        </thead>

        <tbody>
          {result.entities.map((e, i) => {
            const hasCoordinates =
              !!e.position &&
              Number.isFinite(e.position.lon) &&
              Number.isFinite(e.position.lat);

            return (
              <tr key={e.entityId}>
                <td className="mono">
                  #{i + 1}
                </td>

                <td>
                  <div style={{ fontWeight: i === 0 ? 700 : 500 }}>{e.label}</div>
                  <div className="mono muted" style={{ fontSize: 9.5 }}>
                    {e.entityId}
                  </div>
                </td>

                <td
                  className="num"
                  style={{
                    color:
                      i === 0
                        ? "var(--warn)"
                        : undefined,
                    fontWeight: i === 0 ? 700 : 500
                  }}
                >
                  {e.score != null ? e.score.toFixed(1) : "Optimal"}
                </td>

                <td style={{ textAlign: "right" }}>
                  <div style={{ display: "inline-flex", gap: 4 }}>
                    <button
                      className="btn ghost"
                      style={{ padding: "2px 6px", fontSize: 10 }}
                      onClick={() => inspectResult(e)}
                      disabled={!hasCoordinates}
                      title="Inspect parcel details and 3D camera"
                    >
                      Inspect
                    </button>
                    <button
                      className="btn ghost"
                      style={{ padding: "2px 6px", fontSize: 10 }}
                      onClick={() => flyToResult(e)}
                      disabled={!hasCoordinates}
                      title="Fly Cesium camera to entity"
                    >
                      Fly
                    </button>
                    <button
                      className="btn ghost"
                      style={{ padding: "2px 6px", fontSize: 10 }}
                      onClick={() => handleAddToScenario(e)}
                      title="Add to active scenario basket"
                    >
                      +Plan
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* Explanation Section */}
      {result.explanation && (
        <>
          <SectionTitle>Decision Rationale & Explanation</SectionTitle>
          <div
            style={{
              fontSize: 11.5,
              lineHeight: 1.6,
              background: "rgba(0,0,0,0.25)",
              border: "1px solid var(--line-soft)",
              padding: "9px 11px",
              borderRadius: "6px"
            }}
            className="muted"
          >
            {result.explanation}
          </div>
        </>
      )}

      {/* Contextual Next Step */}
      <NextAction
        title="DECISION ADVANCEMENT"
        prompt={
          topEntity
            ? `Candidate #${topEntity.label} selected. Validate constraints in Inspector or commit directly to ${activeScenario?.name}.`
            : "Review engine recommendations and proceed to constraint validation."
        }
        actionLabel="Inspect Selected Candidate"
        onAction={() => {
          if (topEntity) inspectResult(topEntity);
        }}
        targetWindow="inspector"
        secondaryActionLabel="Add to Scenario"
        onSecondaryAction={async () => {
          if (topEntity) await handleAddToScenario(topEntity);
        }}
        secondaryTargetWindow="changes"
        variant="good"
      />

      {/* Provenance Footer */}
      <div className="hr" />
      <div className="kv">
        <span className="k">Result ID</span>
        <span className="v mono">{result.resultId}</span>
      </div>
      <div className="kv">
        <span className="k">Dataset / Scenario</span>
        <span className="v mono">{result.datasetVersion} · {result.scenarioVersion}</span>
      </div>
    </div>
  );
}
