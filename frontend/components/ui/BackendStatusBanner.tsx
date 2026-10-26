"use client";

import { useEffect } from "react";
import { checkBackend, onBackendStatus } from "@/lib/api/client";
import { useMapStore } from "@/stores/map-store";
import { useRouteAnalysisStore } from "@/stores/route-analysis-store";

/**
 * Synchronizes backend readiness across mapStore and routeAnalysisStore on mount
 * and periodic probe, exposing an accessible live-region status without covering
 * top navigation controls (visual Demo Mode / Live badges render inside TopNavbar
 * and MissionOverview).
 */
export default function BackendStatusBanner() {
  const setDemo = useMapStore((s) => s.setDemo);
  const refreshBackendStatus = useRouteAnalysisStore(
    (s) => s.refreshBackendStatus
  );
  const backendStatus = useRouteAnalysisStore((s) => s.backendStatus);
  const dataMode = useRouteAnalysisStore((s) => s.dataMode);

  useEffect(() => {
    const apply = (up: boolean) => {
      setDemo(!up);
    };
    const off = onBackendStatus(apply);
    void refreshBackendStatus();
    void checkBackend().then(apply);
    const id = setInterval(() => {
      void refreshBackendStatus();
    }, 20000);
    return () => {
      off();
      clearInterval(id);
    };
  }, [refreshBackendStatus, setDemo]);

  return (
    <div className="sr-only" role="status" aria-live="polite">
      {backendStatus.checked
        ? `NagarX active in ${dataMode} mode. ${backendStatus.detail}`
        : "Probing NagarX spatial backend."}
    </div>
  );
}
