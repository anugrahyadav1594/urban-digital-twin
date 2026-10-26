"use client";

import dynamic from "next/dynamic";
import { useEffect } from "react";
import TopNavbar from "./TopNavbar";
import Taskbar from "./Taskbar";
import CommandPalette from "./CommandPalette";
import WindowManager from "./WindowManager";
import MissionOverview from "../overview/MissionOverview";
import RouteWorkflowPanel from "../route-workspace/RouteWorkflowPanel";
import RouteResultsPanel from "../route-workspace/RouteResultsPanel";
import MapOverlayControls from "../route-workspace/MapOverlayControls";
import { checkBackend, onBackendStatus } from "@/lib/api/client";
import { useLayerStore } from "@/stores/layer-store";
import { useScenarioStore } from "@/stores/scenario-store";
import { useRouteAnalysisStore } from "@/stores/route-analysis-store";
import { useWindowStore } from "@/stores/window-store";

/* Client-only Cesium mount — CesiumJS touches window/WebGL on import. */
const CesiumViewer = dynamic(() => import("@/cesium/CesiumViewer"), {
  ssr: false,
  loading: () => (
    <div className="cesium-fallback">
      <div className="mono" style={{ letterSpacing: ".18em", color: "#94a3b8" }}>
        INITIALISING 3D URBAN DIGITAL TWIN...
      </div>
    </div>
  ),
});

interface WorkspaceProps {
  initialView?: "overview" | "map";
}

export default function Workspace({ initialView }: WorkspaceProps) {
  const loadScenarios = useScenarioStore((s) => s.loadScenarios);
  const syncLayers = useLayerStore((s) => s.syncFromBackend);

  const workspaceView = useRouteAnalysisStore((s) => s.workspaceView);
  const setWorkspaceView = useRouteAnalysisStore((s) => s.setWorkspaceView);
  const studyAreaId = useRouteAnalysisStore((s) => s.studyAreaId);
  const loadStudyArea = useRouteAnalysisStore((s) => s.loadStudyArea);

  const hasOpenFloatingWindows = useWindowStore((s) =>
    Object.values(s.windows).some((w) => w.visible)
  );

  useEffect(() => {
    if (initialView) {
      setWorkspaceView(initialView);
    }
  }, [initialView, setWorkspaceView]);

  useEffect(() => {
    void loadStudyArea(studyAreaId);
    void checkBackend().then((up) => {
      if (up) {
        void loadScenarios();
        void syncLayers();
      }
    });
    const unsubscribe = onBackendStatus((up) => {
      if (up) {
        void loadScenarios();
        void syncLayers();
      }
    });
    return unsubscribe;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="nx-app-shell">
      <TopNavbar
        onOpenPalette={() => window.dispatchEvent(new Event("nagarx:palette"))}
      />

      <main className="nx-main-stage">
        {/* Keep Cesium mounted underneath so view switching preserves WebGL camera */}
        <div
          className="nx-cesium-layer"
          style={{
            visibility: workspaceView === "map" ? "visible" : "hidden",
            pointerEvents: workspaceView === "map" ? "auto" : "none",
          }}
          aria-hidden={workspaceView !== "map"}
        >
          <CesiumViewer />
        </div>

        {workspaceView === "overview" ? (
          <MissionOverview />
        ) : (
          <>
            <RouteWorkflowPanel />
            <RouteResultsPanel />
            <MapOverlayControls />
            <WindowManager />
            {hasOpenFloatingWindows && <Taskbar />}
          </>
        )}
      </main>

      <CommandPalette />
    </div>
  );
}
