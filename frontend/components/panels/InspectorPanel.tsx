"use client";

import { useSelectionStore } from "@/stores/selection-store";
import { useWindowStore } from "@/stores/window-store";
import { useScenarioStore } from "@/stores/scenario-store";
import { useAnalysisStore } from "@/stores/analysis-store";
import { mapBridge } from "@/cesium/map-bridge";
import NextAction from "@/components/workflow/NextAction";
import { KV, SectionTitle, Empty } from "@/components/ui/Bits";

export default function InspectorPanel() {
  const { feature, loading, history, select } = useSelectionStore();
  const openWindow = useWindowStore((s) => s.openWindow);
  const { addChange, activeId: activeScenarioId, scenarios } = useScenarioStore();
  const results = useAnalysisStore((s) => s.results);

  const activeScenario = scenarios.find((s) => s.id === activeScenarioId) ?? scenarios[0];

  if (loading) {
    return (
      <Empty>
        <span className="pulse">resolving feature from spatial database…</span>
      </Empty>
    );
  }

  if (!feature) {
    return (
      <div>
        <Empty>
          Click any candidate site, parcel, road, public facility, or hazard in the 3D twin to inspect its attributes, KPIs, and available decisions.
        </Empty>

        <NextAction
          title="INSPECTOR GUIDE"
          prompt="Select an entity on the map or pick a ranked candidate from analysis results."
          actionLabel="View Analysis Results"
          targetWindow="results"
          autoAdvanceWorkflow={false}
        />
      </div>
    );
  }

  // Detect feature context & attributes
  const isCandidate = feature.kind === "candidate" || feature.id.startsWith("cand_") || String(feature.attributes.score || "").length > 0;
  const isRoad = feature.kind === "road" || feature.id.startsWith("road:") || feature.id.includes("link");
  const isFacility = feature.kind === "facility" || feature.id.startsWith("facility:") || feature.id.startsWith("pf_");
  const isParcel = feature.kind === "parcel" || feature.id.startsWith("parcel:");

  // Find matching result entity if available
  let matchedEntity = null;
  for (const r of results) {
    const found = r.entities?.find((e) => e.entityId === feature.id || e.label === feature.name);
    if (found) {
      matchedEntity = found;
      break;
    }
  }

  const floodRisk = String(feature.attributes.flood || feature.attributes.flood_risk || "Low");
  const zoning = String(feature.attributes.zoning || feature.attributes.zone || "N/A");

  const handleAddToScenario = async () => {
    await addChange({
      type: isRoad ? "road" : isFacility ? "facility" : "facility",
      label: `${feature.name} proposal`,
      detail: `${feature.kind} · zoning: ${zoning} · flood risk: ${floodRisk}`,
      object_id: Number(feature.id.replace(/[^0-9]/g, "")) || undefined,
      parameters: {
        id: feature.id,
        attributes: feature.attributes,
        position: feature.position
      }
    });
    openWindow("changes");
  };

  return (
    <div>
      {/* Header Badge */}
      <div className="row" style={{ marginBottom: 8 }}>
        <div>
          <div style={{ fontSize: 15, fontWeight: 700, color: "#fff" }}>{feature.name}</div>
          <div className="mono muted" style={{ fontSize: 10.5 }}>
            {feature.id} · {feature.kind}
          </div>
        </div>
        <span className="chip info">{feature.kind.toUpperCase()}</span>
      </div>

      {/* Primary Action Buttons */}
      <div style={{ display: "flex", gap: 6, margin: "10px 0" }}>
        <button
          className="btn primary"
          style={{ flex: 1, padding: "5px 8px", fontSize: 11 }}
          onClick={() => mapBridge.flyTo(feature.id)}
        >
          Fly to ⊙
        </button>

        <button
          className="btn ghost"
          style={{ flex: 1, padding: "5px 8px", fontSize: 11 }}
          onClick={handleAddToScenario}
        >
          + Add to {activeScenario?.name ?? "Plan"}
        </button>
      </div>

      {/* Candidate / Matched Analysis Score Box */}
      {(isCandidate || matchedEntity) && (
        <div
          style={{
            margin: "10px 0",
            padding: "9px 11px",
            borderRadius: "7px",
            background: "rgba(56,189,248,0.09)",
            border: "1px solid rgba(56,189,248,0.35)"
          }}
        >
          <div className="row" style={{ marginBottom: 4 }}>
            <span style={{ fontSize: 10, fontFamily: "var(--mono)", color: "var(--accent)", fontWeight: 700 }}>
              ANALYSIS SCORE
            </span>
            <span className="mono" style={{ fontSize: 13, fontWeight: 700, color: "var(--warn)" }}>
              {(matchedEntity?.score ?? Number(feature.attributes.score) ?? 85.0).toFixed(1)} / 100
            </span>
          </div>

          {matchedEntity?.breakdown && (
            <div style={{ fontSize: 10.5, marginTop: 4 }}>
              {Object.entries(matchedEntity.breakdown).map(([k, v]) => (
                <div key={k} style={{ display: "flex", justifyContent: "space-between", margin: "2px 0" }}>
                  <span className="muted">{k}:</span>
                  <span className="mono">{Number(v).toFixed(1)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Specific Context KPIs */}
      <SectionTitle>Contextual KPIs & Safety</SectionTitle>
      <KV k="Zoning" v={zoning} />
      <KV k="Flood Risk" v={floodRisk} />
      {feature.attributes.area && <KV k="Land Area" v={`${feature.attributes.area} m²`} />}
      {feature.attributes.floors && <KV k="Floors / Height" v={`${feature.attributes.floors} floors`} />}
      {feature.attributes.ward && <KV k="Administrative Ward" v={String(feature.attributes.ward)} />}

      {/* Raw Attributes list */}
      <SectionTitle>Attributes</SectionTitle>
      {Object.entries(feature.attributes).map(([k, v]) => (
        <KV key={k} k={k} v={String(v)} />
      ))}

      {/* Position */}
      <SectionTitle>Coordinates</SectionTitle>
      <KV k="Longitude" v={feature.position.lon.toFixed(5)} />
      <KV k="Latitude" v={feature.position.lat.toFixed(5)} />

      {/* Universal Next Action */}
      <NextAction
        title="CONTEXTUAL DECISION"
        prompt={
          isCandidate
            ? "Candidate evaluated. Validate slope and environmental constraints on the backend before adding to scenario."
            : isRoad
            ? "Road segment selected. Analyze network connectivity and travel time impacts."
            : isFacility
            ? "Public facility selected. Evaluate 15-minute response catchment area."
            : "Parcel selected. Use as location for site suitability planning."
        }
        actionLabel={isCandidate ? "Validate Constraints" : isRoad ? "Analyze Network" : "Plan Facility Here"}
        onAction={async () => {
          if (isCandidate) {
            try {
              const { api } = await import("@/lib/api/client");
              const { useWorkflowStore } = await import("@/stores/workflow-store");
              const sessId = useWorkflowStore.getState().context.backendSessionId || "wf_sess_default";
              const vRes = await api.planValidate({ session_id: sessId, candidate_id: feature.id });
              if (vRes?.result) {
                useWorkflowStore.getState().setContext({ activeCandidateId: feature.id, customData: vRes.result });
              }
            } catch (err) {
              console.warn("Backend validation warning:", err);
            }
            openWindow("analysis");
          } else if (isRoad) {
            openWindow("analysis");
          } else {
            openWindow("planning");
          }
        }}
        targetWindow={isCandidate ? "analysis" : isRoad ? "analysis" : "planning"}
        secondaryActionLabel="Add Proposal"
        onSecondaryAction={handleAddToScenario}
        secondaryTargetWindow="changes"
      />

      {/* History */}
      {history.length > 1 && (
        <>
          <SectionTitle>Recent selections</SectionTitle>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
            {history.slice(1).map((h) => (
              <button
                key={h}
                className="chip"
                onClick={() => {
                  select(h);
                  mapBridge.flyTo(h);
                }}
              >
                {h}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
