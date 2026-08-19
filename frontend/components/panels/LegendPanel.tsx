"use client";

import { useLayerStore } from "@/stores/layer-store";
import { useAnalysisStore } from "@/stores/analysis-store";
import { useWorkflowStore } from "@/stores/workflow-store";
import { SectionTitle, Empty } from "@/components/ui/Bits";

export default function LegendPanel() {
  const layers = useLayerStore((s) => s.layers).filter((l) => l.visible && l.legend);
  const activeResult = useAnalysisStore((s) => s.results[0] ?? null);
  const activeWorkflowId = useWorkflowStore((s) => s.activeWorkflowId);

  const hasAnalysisLegend = activeResult?.entities?.length > 0;
  const isStressWorkflow = activeWorkflowId === "stress";

  if (layers.length === 0 && !hasAnalysisLegend && !isStressWorkflow) {
    return <Empty>Enable a dataset layer (land use, population, flood risk) or run an analysis to view map legends.</Empty>;
  }

  return (
    <div>
      {/* Active Workflow / Analysis Context Legend Keys */}
      {isStressWorkflow && (
        <div style={{ marginBottom: 12 }}>
          <SectionTitle>Stress-Test / Disaster Symbols</SectionTitle>
          <div className="layer-row" style={{ padding: "3px 4px" }}>
            <span className="swatch" style={{ background: "#ef4444", width: 14, height: 10 }} />
            <span style={{ fontSize: 12 }}>Road Closed / Impassable</span>
          </div>
          <div className="layer-row" style={{ padding: "3px 4px" }}>
            <span className="swatch" style={{ background: "#fbbf24", width: 14, height: 10 }} />
            <span style={{ fontSize: 12 }}>Road Slowed / Partial Inundation</span>
          </div>
          <div className="layer-row" style={{ padding: "3px 4px" }}>
            <span className="swatch" style={{ background: "#22c55e", width: 14, height: 10 }} />
            <span style={{ fontSize: 12 }}>Reopened by Mitigation Barrier</span>
          </div>
          <div className="layer-row" style={{ padding: "3px 4px" }}>
            <span className="swatch" style={{ background: "#00e5ff", width: 14, height: 10 }} />
            <span style={{ fontSize: 12 }}>Emergency Dispatch Route</span>
          </div>
        </div>
      )}

      {hasAnalysisLegend && (
        <div style={{ marginBottom: 12 }}>
          <SectionTitle>{activeResult.title} — Candidates</SectionTitle>
          <div className="layer-row" style={{ padding: "3px 4px" }}>
            <span className="swatch" style={{ background: "#fde047", width: 14, height: 10 }} />
            <span style={{ fontSize: 12 }}>Recommended Option (#1)</span>
          </div>
          <div className="layer-row" style={{ padding: "3px 4px" }}>
            <span className="swatch" style={{ background: "#38bdf8", width: 14, height: 10 }} />
            <span style={{ fontSize: 12 }}>High Suitability Candidate</span>
          </div>
        </div>
      )}

      {/* Dataset Layers Legends */}
      {layers.map((l) => (
        <div key={l.id} style={{ marginBottom: 12 }}>
          <SectionTitle>{l.name}</SectionTitle>
          {l.legend!.map((e) => (
            <div key={e.label} className="layer-row" style={{ padding: "3px 4px" }}>
              <span className="swatch" style={{ background: e.color, width: 14, height: 10 }} />
              <span style={{ fontSize: 12 }}>{e.label}</span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
