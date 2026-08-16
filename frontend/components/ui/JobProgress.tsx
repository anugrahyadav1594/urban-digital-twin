"use client";
import type { Job } from "@/types";
import { Bar } from "./Bits";

export default function JobProgress({ job }: { job: Job }) {
  return (
    <div style={{ border: "1px solid var(--line-soft)", borderRadius: 6, padding: 9, marginBottom: 8, background: "rgba(255,255,255,.02)" }}>
      <div className="row" style={{ marginBottom: 6 }}>
        <strong style={{ fontSize: 12 }}>{job.title}</strong>
        <span className={"chip " + (job.state === "succeeded" ? "good" : job.state === "failed" ? "bad" : "info")}>{job.state}</span>
      </div>
      {job.stages.map((s) => (
        <div key={s.key} className={"stage " + s.state}>
          <span className="mark">{s.state === "done" ? "✓" : s.state === "running" ? <span className="spin">●</span> : "○"}</span>
          <span>{s.label}</span>
        </div>
      ))}
      <div style={{ marginTop: 8 }}>
        <Bar value={job.progress} />
        <div className="row" style={{ marginTop: 4 }}>
          <span className="muted mono" style={{ fontSize: 10.5 }}>{job.id}</span>
          <span className="mono" style={{ fontSize: 11 }}>{job.progress}%</span>
        </div>
      </div>
    </div>
  );
}
