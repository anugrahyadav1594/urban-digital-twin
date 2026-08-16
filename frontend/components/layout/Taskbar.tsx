"use client";
import { WINDOW_REGISTRY, useWindowStore } from "@/stores/window-store";
import { useMapStore } from "@/stores/map-store";
import { useJobStore } from "@/stores/job-store";
import { useSelectionStore } from "@/stores/selection-store";
import { CITY } from "@/lib/city-model";

export default function Taskbar() {
  const { windows, order, activeId, restoreWindow, focusWindow, minimizeWindow, openWindow } = useWindowStore();
  const { cameraText, ready, year } = useMapStore();
  const jobs = useJobStore((s) => s.jobs);
  const running = jobs.filter((j) => j.state === "running").length;
  const sel = useSelectionStore((s) => s.feature);

  const open = order.map((id) => windows[id]).filter((w) => w && w.visible);

  return (
    <div className="taskbar" suppressHydrationWarning>
      <span className="mono" style={{ color: "var(--txt-faint)", letterSpacing: "0.1em" }} suppressHydrationWarning>WINDOWS</span>
      {open.length === 0 && <span className="muted" suppressHydrationWarning>none open · use the navbar or ⌘K</span>}
      {open.map((w) => (
        <button
          key={w.id}
          className={"task" + (activeId === w.id && !w.minimized ? " on" : "")}
          onClick={() => (w.minimized ? restoreWindow(w.id) : activeId === w.id ? minimizeWindow(w.id) : focusWindow(w.id))}
        >
          <span style={{ color: "var(--accent)" }}>{WINDOW_REGISTRY[w.id].icon}</span>
          {w.title}
          {w.minimized && <span className="muted">–</span>}
        </button>
      ))}

      <div className="status-right" suppressHydrationWarning>
        <button className="task" onClick={() => openWindow("jobs")} title="Job monitor">
          {running > 0 ? <span className="spin">◴</span> : <span>○</span>} {running} running
        </button>
        <span>{sel ? "SEL " + sel.id : "SEL —"}</span>
        <span>YEAR {year}</span>
        <span>{CITY.datasetVersion}</span>
        <span style={{ color: ready ? "var(--good)" : "var(--warn)" }} suppressHydrationWarning>{ready ? "VIEWER OK" : "VIEWER …"}</span>
        <span suppressHydrationWarning>{cameraText || "—"}</span>
      </div>
    </div>
  );
}
