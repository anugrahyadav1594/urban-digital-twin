"use client";

import React, { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { STUDY_AREAS } from "@/lib/routing-engine";
import { useRouteAnalysisStore } from "@/stores/route-analysis-store";
import { useWindowStore, type WindowId } from "@/stores/window-store";

interface Props {
  onOpenPalette: () => void;
}

const ADVANCED_TOOLS: { id: WindowId; label: string; group: string }[] = [
  { id: "layers", label: "Layer Manager & Opacity", group: "Map & Inspection" },
  { id: "inspector", label: "Feature Inspector", group: "Map & Inspection" },
  { id: "regions", label: "Regional Comparison Overlays", group: "Map & Inspection" },
  { id: "emergency", label: "Station-to-Incident Dispatch", group: "Urban Planning Modules" },
  { id: "simulation", label: "Parametric Exposure Simulator", group: "Urban Planning Modules" },
  { id: "analysis", label: "Site Suitability Analysis", group: "Urban Planning Modules" },
  { id: "planning", label: "Road & Zoning Proposals", group: "Urban Planning Modules" },
  { id: "comparison", label: "Scenario Comparison Matrix", group: "Urban Planning Modules" },
  { id: "scorecard", label: "Sector Readiness Scorecard", group: "Diagnostics & AI" },
  { id: "ai", label: "Spatial AI Assistant", group: "Diagnostics & AI" },
  { id: "jobs", label: "Background Job Monitor", group: "Diagnostics & AI" },
];

export default function TopNavbar({ onOpenPalette }: Props) {
  const router = useRouter();
  const pathname = usePathname();

  const {
    workspaceView,
    setWorkspaceView,
    studyAreaId,
    draftScenario,
    dataMode,
    setDataMode,
    backendStatus,
    refreshBackendStatus,
    resetDemo,
    setLeftPanelOpen,
    setRightPanelOpen,
    result,
  } = useRouteAnalysisStore();

  const openWindow = useWindowStore((s) => s.openWindow);
  const openFloatingCount = useWindowStore(
    (s) => Object.values(s.windows).filter((w) => w.visible).length
  );
  const closeAllWindows = useWindowStore((s) => s.closeAll);

  const [openMenu, setOpenMenu] = useState<"status" | "tools" | null>(null);
  const navRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (!navRef.current?.contains(e.target as Node)) {
        setOpenMenu(null);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpenMenu(null);
    };
    window.addEventListener("mousedown", onDocClick);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", onDocClick);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  const area = STUDY_AREAS[studyAreaId];

  const switchView = (view: "overview" | "map") => {
    setWorkspaceView(view);
    if (view === "map" && pathname !== "/workspace") {
      router.push("/workspace");
    }
  };

  return (
    <header ref={navRef} className="nx-topbar" role="banner">
      {/* Brand + View Switcher */}
      <div className="nx-topbar-left">
        <button
          type="button"
          className="nx-brand-btn"
          onClick={() => switchView("overview")}
          title="NagarX Mission Overview"
        >
          <span className="nx-brand-mark" aria-hidden="true" />
          <span className="nx-brand-text">
            <strong>NAGARX</strong>
            <small>DISASTER-AWARE ROUTING</small>
          </span>
        </button>

        <nav className="nx-view-tabs" aria-label="Primary Workspace Views">
          <button
            type="button"
            className={
              "nx-view-tab" + (workspaceView === "overview" ? " active" : "")
            }
            onClick={() => switchView("overview")}
          >
            Overview
          </button>
          <button
            type="button"
            className={
              "nx-view-tab" + (workspaceView === "map" ? " active" : "")
            }
            onClick={() => switchView("map")}
          >
            3D City Workspace
          </button>
        </nav>
      </div>

      {/* Active Study Area, Scenario & Prominent Data Mode Indicator */}
      <div className="nx-topbar-center">
        <button
          type="button"
          className="nx-context-pill"
          onClick={() => {
            switchView("map");
            setLeftPanelOpen(true);
            useRouteAnalysisStore.getState().setWizardStep(1);
          }}
          title="Change Study Area (Step 1)"
        >
          <span className="nx-context-label">Area:</span>
          <strong>{area.shortName}</strong>
        </button>

        <button
          type="button"
          className="nx-context-pill hide-sm"
          onClick={() => {
            switchView("map");
            setLeftPanelOpen(true);
            useRouteAnalysisStore.getState().setWizardStep(3);
          }}
          title="Configure Disaster Scenario (Step 3)"
        >
          <span className="nx-context-label">Scenario:</span>
          <strong>
            {draftScenario.active ? draftScenario.name.slice(0, 26) : "Inactive"}
          </strong>
        </button>

        {/* Data Mode Indicator & Popover */}
        <div className="nx-menu-anchor">
          <button
            type="button"
            className={
              "nx-mode-badge " + (dataMode === "live" ? "live" : "demo")
            }
            onClick={() =>
              setOpenMenu(openMenu === "status" ? null : "status")
            }
            aria-expanded={openMenu === "status"}
            title="Inspect data provenance and backend connection status"
          >
            <span className="nx-mode-dot" aria-hidden="true" />
            <span>
              {dataMode === "live" ? "LIVE · POSTGIS" : "DEMO MODE · SIMULATED"}
            </span>
          </button>

          {openMenu === "status" && (
            <div
              className="nx-dropdown nx-status-popover"
              role="dialog"
              aria-label="Data Mode and Connection Status"
            >
              <div className="nx-pop-title">Data Mode &amp; Provenance</div>
              <p className="nx-pop-desc">{backendStatus.detail}</p>
              <div className="nx-pop-meta mono">
                Active Source: {area.provenance}
              </div>

              <div className="nx-segmented" style={{ marginTop: 10 }}>
                <button
                  type="button"
                  className={
                    "nx-seg-btn" + (dataMode === "demo" ? " active" : "")
                  }
                  onClick={() => setDataMode("demo")}
                >
                  Demo / Local Graph
                </button>
                <button
                  type="button"
                  className={
                    "nx-seg-btn" + (dataMode === "live" ? " active" : "")
                  }
                  disabled={area.isSyntheticBenchmark}
                  onClick={() => setDataMode("live")}
                >
                  Live PostGIS
                </button>
              </div>

              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginTop: 10,
                }}
              >
                <button
                  type="button"
                  className="nx-btn nx-btn-ghost nx-btn-xs"
                  onClick={() => void refreshBackendStatus()}
                >
                  {backendStatus.checking ? "Probing..." : "Re-check Backend"}
                </button>
                <button
                  type="button"
                  className="nx-btn nx-btn-secondary nx-btn-xs"
                  onClick={() => setOpenMenu(null)}
                >
                  Close
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Right Actions */}
      <div className="nx-topbar-right">
        {workspaceView === "map" && result && (
          <button
            type="button"
            className="nx-btn nx-btn-ghost nx-btn-xs hide-md"
            onClick={() => setRightPanelOpen(true)}
          >
            Results
          </button>
        )}

        <button
          type="button"
          className="nx-btn nx-btn-ghost nx-btn-xs"
          onClick={onOpenPalette}
          title="Open Command & Search Palette (Ctrl+K)"
          aria-label="Open Command Palette"
        >
          Search <kbd className="nx-kbd">⌘K</kbd>
        </button>

        {/* Advanced Floating Modules */}
        <div className="nx-menu-anchor">
          <button
            type="button"
            className="nx-btn nx-btn-ghost nx-btn-xs"
            onClick={() => setOpenMenu(openMenu === "tools" ? null : "tools")}
            aria-expanded={openMenu === "tools"}
          >
            Tools{openFloatingCount > 0 ? ` (${openFloatingCount})` : ""} ▾
          </button>

          {openMenu === "tools" && (
            <div
              className="nx-dropdown nx-tools-dropdown"
              role="menu"
              aria-label="Advanced Urban Twin Modules"
            >
              <div className="nx-pop-title">Advanced Digital Twin Modules</div>
              <p className="nx-pop-desc" style={{ marginBottom: 8 }}>
                Optional floating windows for broader urban planning workflows.
              </p>
              {ADVANCED_TOOLS.map((tool) => (
                <button
                  key={tool.id}
                  type="button"
                  role="menuitem"
                  className="nx-tool-item"
                  onClick={() => {
                    switchView("map");
                    openWindow(tool.id);
                    setOpenMenu(null);
                  }}
                >
                  <span>{tool.label}</span>
                  <small>{tool.group}</small>
                </button>
              ))}
              {openFloatingCount > 0 && (
                <button
                  type="button"
                  role="menuitem"
                  className="nx-tool-item danger"
                  onClick={() => {
                    closeAllWindows();
                    setOpenMenu(null);
                  }}
                >
                  <span>Close All Floating Windows</span>
                  <small>{openFloatingCount} open</small>
                </button>
              )}
            </div>
          )}
        </div>

        <button
          type="button"
          className="nx-btn nx-btn-secondary nx-btn-xs"
          onClick={() => void resetDemo()}
          title="Reset workspace to clean Demonstration Flood Scenario"
        >
          Reset Demo
        </button>
      </div>
    </header>
  );
}
