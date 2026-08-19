"use client";
import type { Metric } from "@/types";

export function SectionTitle({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return <div className="sec-title" style={style}>{children}</div>;
}

export function KV({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="kv">
      <span className="k">{k}</span>
      <span className="v">{v}</span>
    </div>
  );
}

export function MetricCards({ metrics }: { metrics: Metric[] }) {
  return (
    <div className="metrics">
      {metrics.map((m) => {
        const good = m.delta === undefined ? null : (m.better === "down" ? m.delta < 0 : m.delta > 0);
        return (
          <div className="metric" key={m.key}>
            <div className="l">{m.label}</div>
            <div className="v">
              {m.value}
              {m.unit && <span style={{ fontSize: 11, color: "var(--txt-dim)" }}> {m.unit}</span>}
            </div>
            {m.delta !== undefined && (
              <div className="d" style={{ color: good ? "var(--good)" : "var(--bad)" }}>
                {m.delta > 0 ? "+" : ""}{m.delta}%
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function Bar({ value, max = 100 }: { value: number; max?: number }) {
  return <div className="bar"><i style={{ width: Math.max(2, Math.min(100, (value / max) * 100)) + "%" }} /></div>;
}

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="field">
      <label>{label}</label>
      {children}
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="muted" style={{ padding: "22px 8px", textAlign: "center", lineHeight: 1.6 }}>{children}</div>;
}
