"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/constants";
import { checkBackend, onBackendStatus } from "@/lib/api/client";
import { useMapStore } from "@/stores/map-store";

/**
 * Unmissable banner when the backend is unreachable.
 *
 * The API client falls back to deterministic in-memory data so the UI keeps
 * working offline. Without this banner that fallback is invisible, and demo
 * numbers look exactly like real analysis of your PostGIS database.
 */
export default function BackendStatusBanner() {
  const [up, setUp] = useState<boolean | null>(null);
  const [checking, setChecking] = useState(false);
  const setDemo = useMapStore((s) => s.setDemo);

  useEffect(() => {
    const apply = (v: boolean) => { setUp(v); setDemo(!v); };
    const off = onBackendStatus(apply);
    checkBackend().then(apply);
    const id = setInterval(() => { checkBackend().then(apply); }, 15000);
    return () => { off(); clearInterval(id); };
  }, [setDemo]);

  async function retry() {
    setChecking(true);
    const v = await checkBackend();
    setUp(v); setDemo(!v);
    setChecking(false);
  }

  if (up === null || up === true) return null;

  return (
    <div
      role="alert"
      style={{
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 9999,
        background: "repeating-linear-gradient(45deg,#7f1d1d,#7f1d1d 12px,#991b1b 12px,#991b1b 24px)",
        color: "#fff", padding: "8px 14px", fontSize: 13,
        fontFamily: "ui-monospace, monospace", display: "flex",
        alignItems: "center", gap: 12, borderBottom: "2px solid #ef4444",
        boxShadow: "0 2px 12px rgba(0,0,0,.45)"
      }}
    >
      <strong style={{ letterSpacing: ".5px" }}>DEMO DATA</strong>
      <span style={{ opacity: 0.95 }}>
        Backend unreachable at <code>{API_BASE}</code> — figures below are
        synthetic, not from your database.
      </span>
      <button
        onClick={retry}
        disabled={checking}
        style={{
          marginLeft: "auto", background: "#fff", color: "#7f1d1d",
          border: 0, borderRadius: 4, padding: "3px 12px",
          fontWeight: 700, cursor: checking ? "wait" : "pointer", fontSize: 12
        }}
      >
        {checking ? "checking…" : "Retry"}
      </button>
    </div>
  );
}
