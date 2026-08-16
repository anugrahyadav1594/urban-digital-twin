"use client";
import { useEffect, useState } from "react";
import { PRESETS, useWindowStore, type WindowId } from "@/stores/window-store";
import { useMapStore } from "@/stores/map-store";
import { useScenarioStore } from "@/stores/scenario-store";
import { mapBridge } from "@/cesium/map-bridge";

type Group = { label: string; items: { id: WindowId; label: string; kbd?: string }[] };

const GROUPS: Group[] = [
  { label: "City", items: [{ id: "city", label: "City information" }, { id: "layers", label: "Dataset layers", kbd: "⌘ 1" }] },
  { label: "Scenario", items: [{ id: "scenario", label: "Scenario manager", kbd: "⌘ 4" }, { id: "changes", label: "Scenario changes" }] },
  { label: "Layers", items: [{ id: "layers", label: "Layer manager", kbd: "⌘ 1" }, { id: "legend", label: "Legend" }] },
  { label: "Planning", items: [{ id: "planning", label: "Site suitability / tools", kbd: "⌘ 2" }, { id: "inspector", label: "Object inspector" }] },
  { label: "Analysis", items: [{ id: "analysis", label: "Analysis", kbd: "⌘ 3" }, { id: "results", label: "Results" }] },
  { label: "Simulation", items: [{ id: "simulation", label: "Simulation controls" }, { id: "jobs", label: "Job monitor" }] },
  { label: "Compare", items: [{ id: "comparison", label: "Scenario comparison", kbd: "⌘ 6" }] },
  { label: "AI", items: [{ id: "ai", label: "Planning assistant", kbd: "⌘ 5" }, { id: "trace", label: "Agent trace" }] }
];

const SearchIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" suppressHydrationWarning><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
);

const HomeIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" suppressHydrationWarning><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
);

const MaximizeIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" suppressHydrationWarning><path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/></svg>
);

const SettingsIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" suppressHydrationWarning><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>
);

const ChevronDownIcon = () => (
  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="chevron-icon" suppressHydrationWarning><path d="m6 9 6 6 6-6"/></svg>
);

const GROUP_ICONS: Record<string, React.ReactNode> = {
  City: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" suppressHydrationWarning><path d="M3 21h18"/><path d="M5 21V7l8-4v18"/><path d="M19 21V11l-6-4"/></svg>,
  Scenario: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" suppressHydrationWarning><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg>,
  Layers: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" suppressHydrationWarning><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>,
  Planning: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" suppressHydrationWarning><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>,
  Analysis: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" suppressHydrationWarning><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>,
  Simulation: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" suppressHydrationWarning><polygon points="5 3 19 12 5 21 5 3"/></svg>,
  Compare: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" suppressHydrationWarning><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M12 3v18"/></svg>,
  AI: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" suppressHydrationWarning><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3L12 3z"/></svg>
};

const WorkspaceIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" suppressHydrationWarning><rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/></svg>
);

export default function TopNavbar() {
  const [open, setOpen] = useState<string | null>(null);
      const { openWindow, applyPreset, closeAll, autoArrangeWindows } = useWindowStore();
  const { demo, ready } = useMapStore();
  const { scenarios, activeId, setActive } = useScenarioStore();

  useEffect(() => {
    const close = () => setOpen(null);
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, []);

  const openPalette = () => window.dispatchEvent(new CustomEvent("nagarx:palette"));

  return (
    <div className="navbar" onClick={(e) => e.stopPropagation()} suppressHydrationWarning>
      <div className="brand"><span className="dot" />NAGAR-X</div>
      <div className="nav-sep" />

      {GROUPS.map((g) => (
        <div key={g.label} style={{ position: "relative" }}>
          <button className={"navitem" + (open === g.label ? " active" : "")} onClick={() => setOpen(open === g.label ? null : g.label)}>
            {GROUP_ICONS[g.label]}
            <span>{g.label}</span>
            <ChevronDownIcon />
          </button>
          {open === g.label && (
            <div className="menu">
              {g.items.map((it) => (
                <button key={it.id + it.label} onClick={() => { openWindow(it.id); setOpen(null); }}>
                  <span>{it.label}</span>
                  {it.kbd && <span className="kbd">{it.kbd}</span>}
                </button>
              ))}
            </div>
          )}
        </div>
      ))}

      <div className="nav-sep" />

      <div style={{ position: "relative" }}>
        <button className={"navitem" + (open === "ws" ? " active" : "")} onClick={() => setOpen(open === "ws" ? null : "ws")}>
          <WorkspaceIcon />
          <span>Workspace</span>
          <ChevronDownIcon />
        </button>
        {open === "ws" && (
          <div className="menu">
            <div className="sec">Presets</div>
            {Object.keys(PRESETS).map((p) => (
              <button key={p} onClick={() => { applyPreset(p); setOpen(null); }}>{p}</button>
            ))}
            <div className="sec">Layout</div>
            <button onClick={() => { autoArrangeWindows(); setOpen(null); }}>Auto-align open windows</button>
            <button onClick={() => { closeAll(); setOpen(null); }}>Close all windows</button>
            <button onClick={() => { localStorage.removeItem("nagarx.workspace.layout.v1"); location.reload(); }}>Reset saved layout</button>
          </div>
        )}
      </div>

      <div className="nav-right">
        <select className="input" style={{ width: 190, padding: "5px 10px", fontSize: 13, borderRadius: 7, height: 34 }} value={activeId} onChange={(e) => setActive(e.target.value)} title="Active scenario">
          {scenarios.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        {demo && <span className="badge-demo">DEMO DATA</span>}
        <button className="search" onClick={openPalette}>
          <SearchIcon /><span>Search</span><span className="kbd">{"⌘K"}</span>
        </button>
        <button className="icon-btn" title="Fly to city" onClick={() => mapBridge.home()}><HomeIcon /></button>
        <button className="icon-btn" title="Fullscreen" onClick={() => (document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen())}><MaximizeIcon /></button>
        <button className="icon-btn" title="Settings" onClick={() => openWindow("city")}><SettingsIcon /></button>
        <span className="chip" title={ready ? "Viewer ready" : "Viewer loading"} style={{ borderColor: ready ? "rgba(52,211,153,.35)" : undefined, color: ready ? "var(--good)" : undefined }}>&#9679;</span>
      </div>
    </div>
  );
}
