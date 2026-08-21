"use client";

import React, { useState } from "react";

interface WorkflowErrorStateProps {
  error: Error | string | null;
  step?: string;
  onRetry?: () => void | Promise<void>;
  onBack?: () => void;
  title?: string;
}

export default function WorkflowErrorState({
  error,
  step,
  onRetry,
  onBack,
  title = "WORKFLOW ERROR"
}: WorkflowErrorStateProps) {
  const [expanded, setExpanded] = useState(false);
  const [retrying, setRetrying] = useState(false);

  if (!error) return null;

  const errorMessage = typeof error === "string" ? error : error.message || "An unexpected workflow error occurred.";
  const errCode = (error as any)?.code;
  const errDetails = (error as any)?.details;
  const errStep = step || (error as any)?.step;

  const handleRetry = async () => {
    if (!onRetry || retrying) return;
    setRetrying(true);
    try {
      await onRetry();
    } catch {
      // error handled by caller
    } finally {
      setRetrying(false);
    }
  };

  return (
    <div
      style={{
        margin: "10px 0",
        padding: "10px 12px",
        borderRadius: "8px",
        background: "rgba(239, 68, 68, 0.12)",
        border: "1px solid rgba(239, 68, 68, 0.4)",
        boxShadow: "0 4px 14px rgba(0,0,0,0.3)"
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
              color: "#fca5a5",
              textTransform: "uppercase"
            }}
          >
            {title}
          </span>
          {errStep && (
            <span className="mono muted" style={{ fontSize: 9.5 }}>
              · Step: {errStep}
            </span>
          )}
        </div>
        {errCode && (
          <span className="chip warn" style={{ fontSize: 9.5, padding: "1px 6px" }}>
            {errCode}
          </span>
        )}
      </div>

      <div
        style={{
          fontSize: 11.5,
          lineHeight: 1.45,
          color: "#fecdd3",
          marginBottom: 8
        }}
      >
        {errorMessage}
      </div>

      {(errDetails || typeof error === "object") && (
        <div style={{ marginBottom: 8 }}>
          <button
            className="btn ghost"
            style={{ fontSize: 10, padding: "1px 6px", color: "var(--txt-dim)" }}
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? "Hide Technical Details ▴" : "Show Technical Details ▾"}
          </button>
          {expanded && (
            <pre
              style={{
                marginTop: 6,
                padding: "6px 8px",
                borderRadius: "4px",
                background: "rgba(0,0,0,0.4)",
                fontSize: 10,
                color: "var(--txt-dim)",
                whiteSpace: "pre-wrap",
                wordBreak: "break-all"
              }}
            >
              {JSON.stringify({ code: errCode, step: errStep, details: errDetails, raw: String(error) }, null, 2)}
            </pre>
          )}
        </div>
      )}

      <div style={{ display: "flex", gap: 6 }}>
        {onRetry && (
          <button
            className="btn primary"
            style={{
              flex: 1,
              padding: "4px 8px",
              fontSize: 11,
              background: "#ef4444",
              borderColor: "#f87171"
            }}
            onClick={handleRetry}
            disabled={retrying}
          >
            {retrying ? "RETRYING…" : "RETRY ACTION ↻"}
          </button>
        )}
        {onBack && (
          <button
            className="btn ghost"
            style={{ padding: "4px 8px", fontSize: 11 }}
            onClick={onBack}
          >
            BACK ◀
          </button>
        )}
      </div>
    </div>
  );
}
