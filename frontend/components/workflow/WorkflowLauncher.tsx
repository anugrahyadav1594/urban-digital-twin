"use client";

import React from "react";
import { WORKFLOWS, type WorkflowId } from "@/lib/workflows";
import { useWorkflowStore } from "@/stores/workflow-store";

interface WorkflowLauncherProps {
  onClose?: () => void;
}

export default function WorkflowLauncher({ onClose }: WorkflowLauncherProps) {
  const { activeWorkflowId, startWorkflow, currentStepIndex } = useWorkflowStore();

  const handleStart = (id: WorkflowId) => {
    startWorkflow(id, activeWorkflowId === id ? currentStepIndex : 0);
    if (onClose) onClose();
  };

  const workflowList = Object.values(WORKFLOWS);

  return (
    <div
      style={{
        padding: "14px",
        maxHeight: "75vh",
        overflowY: "auto"
      }}
    >
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: "#fff", letterSpacing: ".02em" }}>
          Planner Decision Workflows
        </div>
        <div className="muted" style={{ fontSize: 11.5, marginTop: 3 }}>
          Structured, goal-oriented decision paths connecting deterministic GIS, simulations, routing, and scenario changes.
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {workflowList.map((wf) => {
          const isActive = activeWorkflowId === wf.id;

          return (
            <div
              key={wf.id}
              style={{
                background: isActive ? "rgba(56, 189, 248, 0.09)" : "rgba(255, 255, 255, 0.02)",
                border: isActive ? "1.5px solid var(--accent)" : "1px solid var(--line)",
                borderRadius: "9px",
                padding: "12px",
                transition: "all 0.2s ease"
              }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 6 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 18 }}>{wf.icon}</span>
                  <div>
                    <div style={{ fontSize: 13.5, fontWeight: 700, color: "#fff" }}>
                      {wf.title}
                    </div>
                    <span className="chip info" style={{ fontSize: 9.5, padding: "1px 6px", marginTop: 2 }}>
                      {wf.badge}
                    </span>
                  </div>
                </div>

                <button
                  className={isActive ? "btn primary" : "btn"}
                  style={{
                    padding: "4px 12px",
                    fontSize: 11,
                    fontWeight: 600
                  }}
                  onClick={() => handleStart(wf.id)}
                >
                  {isActive ? "Resume Workflow ▶" : "Start Workflow →"}
                </button>
              </div>

              <div style={{ fontSize: 11.5, color: "var(--txt-dim)", lineHeight: 1.45, margin: "6px 0 8px" }}>
                {wf.summary}
              </div>

              {/* Step preview pills */}
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 8 }}>
                {wf.steps.map((st, i) => (
                  <span
                    key={st.id}
                    className="chip"
                    style={{
                      fontSize: 10,
                      padding: "2px 6px",
                      background: "rgba(0,0,0,0.35)",
                      color: "var(--txt-dim)"
                    }}
                  >
                    {i + 1}. {st.shortLabel}
                  </span>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
