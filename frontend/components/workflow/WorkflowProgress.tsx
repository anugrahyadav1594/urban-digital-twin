"use client";

import React, { useState } from "react";
import { useWorkflowStore } from "@/stores/workflow-store";
import { useWindowStore } from "@/stores/window-store";

export default function WorkflowProgress() {
  const {
    activeWorkflowId,
    currentStepIndex,
    completedStepIds,
    currentWorkflow,
    currentStep,
    advanceStep,
    prevStep,
    jumpToStep,
    cancelWorkflow
  } = useWorkflowStore();

  const [collapsed, setCollapsed] = useState(false);
  const openWindow = useWindowStore((s) => s.openWindow);

  const wf = currentWorkflow();
  const step = currentStep();

  if (!activeWorkflowId || !wf) return null;

  return (
    <div
      style={{
        position: "absolute",
        top: 76,
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 8900,
        width: "min(960px, 94vw)",
        background: "rgba(13, 19, 30, 0.94)",
        border: "1px solid rgba(56, 189, 248, 0.35)",
        boxShadow: "0 10px 30px rgba(0, 0, 0, 0.65), 0 0 16px rgba(56, 189, 248, 0.12)",
        borderRadius: "10px",
        backdropFilter: "blur(16px)",
        padding: collapsed ? "6px 14px" : "10px 14px",
        transition: "all 0.25s cubic-bezier(0.16, 1, 0.3, 1)"
      }}
    >
      {/* Header bar */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 14 }}>{wf.icon}</span>
          <span
            style={{
              fontFamily: "var(--sans)",
              fontWeight: 700,
              fontSize: 13,
              letterSpacing: ".02em",
              color: "#fff"
            }}
          >
            {wf.title}
          </span>
          <span className="chip info" style={{ fontSize: 10, padding: "2px 7px" }}>
            Step {currentStepIndex + 1} of {wf.steps.length}
          </span>
          {step && (
            <span className="mono muted" style={{ fontSize: 11 }}>
              — {step.label}
            </span>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {step?.targetWindow && (
            <button
              className="btn ghost"
              style={{ fontSize: 10.5, padding: "2px 7px" }}
              onClick={() => openWindow(step.targetWindow)}
              title="Bring active tool window to front"
            >
              Show Tool ↗
            </button>
          )}

          <button
            className="btn ghost"
            style={{ fontSize: 10.5, padding: "2px 7px" }}
            onClick={() => setCollapsed(!collapsed)}
            title={collapsed ? "Expand workflow steps" : "Collapse"}
          >
            {collapsed ? "Expand ▾" : "Collapse ▴"}
          </button>

          <button
            className="btn ghost"
            style={{ fontSize: 10.5, padding: "2px 7px", color: "var(--txt-dim)" }}
            onClick={cancelWorkflow}
            title="Exit active workflow"
          >
            Exit ✕
          </button>
        </div>
      </div>

      {/* Expanded Stepper */}
      {!collapsed && (
        <div style={{ marginTop: 10 }}>
          {/* Steps strip */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: `repeat(${wf.steps.length}, 1fr)`,
              gap: 6,
              marginBottom: 10
            }}
          >
            {wf.steps.map((s, idx) => {
              const isCurrent = idx === currentStepIndex;
              const isCompleted = completedStepIds.includes(s.id);
              const isPast = idx < currentStepIndex || isCompleted;

              return (
                <div
                  key={s.id}
                  onClick={() => {
                    if (idx <= currentStepIndex || completedStepIds.includes(s.id)) {
                      jumpToStep(idx);
                    }
                  }}
                  style={{
                    padding: "6px 8px",
                    borderRadius: "6px",
                    cursor: "pointer",
                    background: isCurrent
                      ? "rgba(56, 189, 248, 0.16)"
                      : isCompleted
                      ? "rgba(52, 211, 153, 0.08)"
                      : "rgba(255, 255, 255, 0.03)",
                    border: isCurrent
                      ? "1px solid var(--accent)"
                      : isCompleted
                      ? "1px solid rgba(52, 211, 153, 0.35)"
                      : "1px solid var(--line)",
                    transition: "all 0.15s ease"
                  }}
                  title={s.description}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 2 }}>
                    <span
                      style={{
                        width: 16,
                        height: 16,
                        borderRadius: "50%",
                        fontSize: 9.5,
                        fontWeight: 700,
                        display: "inline-flex",
                        alignItems: "center",
                        justifyContent: "center",
                        background: isCurrent
                          ? "var(--accent)"
                          : isCompleted
                          ? "var(--good)"
                          : "var(--line)",
                        color: isCurrent || isCompleted ? "#000" : "var(--txt-dim)"
                      }}
                    >
                      {isCompleted ? "✓" : idx + 1}
                    </span>
                    <span
                      style={{
                        fontSize: 11,
                        fontWeight: isCurrent ? 700 : 500,
                        color: isCurrent ? "var(--txt)" : isPast ? "var(--txt-dim)" : "var(--txt-faint)",
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis"
                      }}
                    >
                      {s.shortLabel}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Prompt & Nav actions */}
          {step && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "6px 10px",
                background: "rgba(0, 0, 0, 0.28)",
                borderRadius: "6px",
                border: "1px solid var(--line-soft)"
              }}
            >
              <div style={{ flex: 1, marginRight: 12 }}>
                <span className="mono" style={{ fontSize: 10, color: "var(--accent)", marginRight: 6 }}>
                  GOAL:
                </span>
                <span style={{ fontSize: 11.5, color: "var(--txt)" }}>{step.actionPrompt}</span>
              </div>

              <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                <button
                  className="btn ghost"
                  style={{ fontSize: 10.5, padding: "3px 9px" }}
                  onClick={prevStep}
                  disabled={currentStepIndex === 0}
                >
                  ◀ Back
                </button>
                <button
                  className="btn primary"
                  style={{ fontSize: 10.5, padding: "3px 10px" }}
                  onClick={advanceStep}
                >
                  {currentStepIndex === wf.steps.length - 1 ? "Complete Workflow ✓" : "Next Step ▶"}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
