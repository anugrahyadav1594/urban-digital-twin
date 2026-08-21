"use client";

import React, { useState } from "react";
import { useWorkflowStore } from "@/stores/workflow-store";
import { useWindowStore, type WindowId } from "@/stores/window-store";
import WorkflowErrorState from "./WorkflowErrorState";

interface NextActionProps {
  title?: string;
  prompt: string;
  actionLabel: string;
  onAction?: () => void | Promise<void>;
  targetWindow?: WindowId;
  secondaryActionLabel?: string;
  onSecondaryAction?: () => void | Promise<void>;
  secondaryTargetWindow?: WindowId;
  autoAdvanceWorkflow?: boolean;
  badge?: string;
  variant?: "primary" | "accent" | "good" | "warn";
  disabled?: boolean;
}

export default function NextAction({
  title = "NEXT STEP",
  prompt,
  actionLabel,
  onAction,
  targetWindow,
  secondaryActionLabel,
  onSecondaryAction,
  secondaryTargetWindow,
  badge,
  variant = "accent",
  disabled = false
}: NextActionProps) {
  const { currentWorkflow, currentStep } = useWorkflowStore();
  const openWindow = useWindowStore((s) => s.openWindow);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | string | null>(null);

  const wf = currentWorkflow();
  const step = currentStep();

  const handlePrimaryClick = async () => {
    if (disabled || loading) return;
    setError(null);
    setLoading(true);
    try {
      if (onAction) {
        await onAction();
      }
      if (targetWindow) {
        openWindow(targetWindow);
      }
    } catch (err: any) {
      console.warn("Workflow action failed:", err);
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSecondaryClick = async () => {
    if (onSecondaryAction) {
      try {
        await onSecondaryAction();
      } catch (err: any) {
        console.warn("Secondary workflow action failed:", err);
        setError(err);
      }
    }
    if (secondaryTargetWindow) {
      openWindow(secondaryTargetWindow);
    }
  };

  const borderColors = {
    primary: "rgba(56, 189, 248, 0.4)",
    accent: "rgba(34, 211, 238, 0.4)",
    good: "rgba(52, 211, 153, 0.4)",
    warn: "rgba(251, 191, 36, 0.4)"
  };

  const bgColors = {
    primary: "rgba(56, 189, 248, 0.08)",
    accent: "rgba(34, 211, 238, 0.08)",
    good: "rgba(52, 211, 153, 0.08)",
    warn: "rgba(251, 191, 36, 0.08)"
  };

  return (
    <div
      style={{
        margin: "12px 0 6px 0",
        padding: "10px 12px",
        borderRadius: "8px",
        background: bgColors[variant],
        border: `1px solid ${borderColors[variant]}`,
        boxShadow: "0 4px 14px rgba(0,0,0,0.25)"
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
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
            {title}
          </span>
          {wf && step && (
            <span className="mono muted" style={{ fontSize: 9.5 }}>
              · {wf.shortTitle} ({step.shortLabel})
            </span>
          )}
        </div>
        {badge && (
          <span className="chip" style={{ fontSize: 9.5, padding: "1px 6px" }}>
            {badge}
          </span>
        )}
      </div>

      <div
        style={{
          fontSize: 11.5,
          lineHeight: 1.45,
          color: "var(--txt)",
          marginBottom: 9
        }}
      >
        {prompt}
      </div>

      {error && (
        <WorkflowErrorState
          error={error}
          step={step?.shortLabel}
          onRetry={handlePrimaryClick}
          onBack={() => setError(null)}
        />
      )}

      <div style={{ display: "flex", gap: 6 }}>
        <button
          className="btn primary"
          style={{
            flex: 1,
            padding: "5px 10px",
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: ".04em"
          }}
          onClick={handlePrimaryClick}
          disabled={disabled || loading}
        >
          {loading ? "EXECUTING…" : actionLabel}
        </button>

        {secondaryActionLabel && (
          <button
            className="btn ghost"
            style={{
              padding: "5px 10px",
              fontSize: 11
            }}
            onClick={handleSecondaryClick}
            disabled={loading}
          >
            {secondaryActionLabel}
          </button>
        )}
      </div>
    </div>
  );
}
