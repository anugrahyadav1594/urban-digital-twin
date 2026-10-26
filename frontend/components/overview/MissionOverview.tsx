"use client";

import React from "react";
import { useRouter, usePathname } from "next/navigation";
import { STUDY_AREAS } from "@/lib/routing-engine";
import { useMapStore } from "@/stores/map-store";
import { useRouteAnalysisStore } from "@/stores/route-analysis-store";
import type { StudyAreaId } from "@/types";

export default function MissionOverview() {
  const router = useRouter();
  const pathname = usePathname();

  const {
    studyAreaId,
    datasets,
    datasetLoading,
    dataMode,
    backendStatus,
    scenarios,
    activeScenarioId,
    draftScenario,
    affectedPreview,
    recentRuns,
    setWorkspaceView,
    loadStudyArea,
    selectScenario,
    loadSampleAndStart,
    refreshBackendStatus,
    resetDemo,
  } = useRouteAnalysisStore();

  const mapReady = useMapStore((s) => s.ready);
  const mapError = useMapStore((s) => s.error);

  const activeArea = STUDY_AREAS[studyAreaId];
  const loadedDataset = datasets[studyAreaId];

  const enterMapWorkspace = () => {
    setWorkspaceView("map");
    if (pathname !== "/workspace") {
      router.push("/workspace");
    }
  };

  const handleQuickRunScenario = async (scenarioId: string) => {
    setWorkspaceView("map");
    if (pathname !== "/workspace") {
      router.push("/workspace");
    }
    await loadSampleAndStart(scenarioId);
  };

  const handleSelectStudyArea = async (id: StudyAreaId) => {
    await loadStudyArea(id);
  };

  return (
    <div className="nx-overview-shell" role="region" aria-label="NagarX Mission Overview">
      <div className="nx-overview-container">
        {/* Hero / Mission Header */}
        <header className="nx-overview-hero">
          <div className="nx-overview-eyebrow">
            <span className="nx-pill nx-pill-accent">NAGARX · RESEARCH PROTOTYPE</span>
            <span
              className={
                "nx-pill " +
                (dataMode === "live" ? "nx-pill-live" : "nx-pill-demo")
              }
            >
              {dataMode === "live"
                ? "LIVE MODE · POSTGIS CONNECTED"
                : "DEMO MODE · OFFLINE SIMULATION DATA"}
            </span>
          </div>

          <h1 className="nx-overview-title">
            3D Urban Digital Twin &amp; Disaster-Aware Route Analysis
          </h1>

          <p className="nx-overview-lead">
            NagarX evaluates a single spatial engineering question:{" "}
            <strong>
              &ldquo;When a road corridor or urban zone becomes affected by a
              simulated disaster, how does the navigable route between two
              locations change?&rdquo;
            </strong>{" "}
            It compares baseline shortest paths against hazard-aware alternatives
            on identical topological road graphs using Dijkstra&apos;s algorithm.
          </p>

          <div className="nx-overview-actions">
            <button
              type="button"
              className="nx-btn nx-btn-primary nx-btn-lg"
              onClick={enterMapWorkspace}
            >
              Start Route Analysis →
            </button>
            <button
              type="button"
              className="nx-btn nx-btn-secondary nx-btn-lg"
              onClick={() => handleQuickRunScenario("preset_kalundre_flood")}
            >
              Run Demonstration Flood Scenario
            </button>
            <button
              type="button"
              className="nx-btn nx-btn-ghost"
              onClick={() => void resetDemo()}
            >
              Reset Demo
            </button>
          </div>
        </header>

        {/* Status Grid: Study Area, Active Scenario, Data & Connection Provenance */}
        <section className="nx-overview-grid" aria-label="Workspace Status">
          {/* Card 1: Current Study Area */}
          <div className="nx-card">
            <div className="nx-card-header">
              <span className="nx-card-kicker">CURRENT STUDY AREA</span>
              <span className="nx-badge">
                {activeArea.isSyntheticBenchmark
                  ? "SYNTHETIC BENCHMARK"
                  : "OPENSTREETMAP EXTRACT"}
              </span>
            </div>
            <h2 className="nx-card-title">{activeArea.name}</h2>
            <p className="nx-card-sub">{activeArea.region}</p>
            <p className="nx-card-body">{activeArea.description}</p>

            <div className="nx-stat-strip">
              <div>
                <div className="nx-stat-label">Connected Nodes</div>
                <div className="nx-stat-val mono">
                  {datasetLoading
                    ? "Loading..."
                    : loadedDataset
                    ? loadedDataset.nodeCount.toLocaleString()
                    : "—"}
                </div>
              </div>
              <div>
                <div className="nx-stat-label">Directed Edges</div>
                <div className="nx-stat-val mono">
                  {datasetLoading
                    ? "Loading..."
                    : loadedDataset
                    ? loadedDataset.directedEdgeCount.toLocaleString()
                    : "—"}
                </div>
              </div>
              <div>
                <div className="nx-stat-label">Road Ways</div>
                <div className="nx-stat-val mono">
                  {datasetLoading
                    ? "Loading..."
                    : loadedDataset
                    ? loadedDataset.roads.length.toLocaleString()
                    : "—"}
                </div>
              </div>
            </div>

            <div className="nx-area-switcher">
              {(Object.keys(STUDY_AREAS) as StudyAreaId[]).map((id) => {
                const area = STUDY_AREAS[id];
                const selected = id === studyAreaId;
                return (
                  <button
                    key={id}
                    type="button"
                    className={"nx-chip" + (selected ? " active" : "")}
                    onClick={() => void handleSelectStudyArea(id)}
                  >
                    {area.shortName}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Card 2: Current Scenario Status */}
          <div className="nx-card">
            <div className="nx-card-header">
              <span className="nx-card-kicker">ACTIVE SCENARIO STATUS</span>
              <span
                className={
                  "nx-badge " +
                  (draftScenario.active ? "nx-badge-warn" : "nx-badge-muted")
                }
              >
                {draftScenario.active ? "SIMULATED HAZARD ACTIVE" : "INACTIVE"}
              </span>
            </div>
            <h2 className="nx-card-title">{draftScenario.name}</h2>
            <p className="nx-card-sub">
              Type:{" "}
              <strong style={{ color: "#f8fafc" }}>
                {draftScenario.type.replace("_", " ").toUpperCase()}
              </strong>{" "}
              · Rule:{" "}
              <strong style={{ color: "#f8fafc" }}>
                {draftScenario.severityMode === "closed"
                  ? "Impassable (Exclude edges)"
                  : `${draftScenario.penaltyMultiplier.toFixed(1)}× Cost Penalty`}
              </strong>
            </p>
            <p className="nx-card-body">{draftScenario.description}</p>

            {affectedPreview && (
              <div className="nx-stat-strip">
                <div>
                  <div className="nx-stat-label">Closed Edges</div>
                  <div className="nx-stat-val mono">
                    {affectedPreview.closedEdgeCount}
                  </div>
                </div>
                <div>
                  <div className="nx-stat-label">Penalized Edges</div>
                  <div className="nx-stat-val mono">
                    {affectedPreview.penalizedEdgeCount}
                  </div>
                </div>
                <div>
                  <div className="nx-stat-label">Affected Length</div>
                  <div className="nx-stat-val mono">
                    {affectedPreview.closedLengthM +
                      affectedPreview.penalizedLengthM}{" "}
                    m
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Card 3: Data Availability & Connection Status */}
          <div className="nx-card">
            <div className="nx-card-header">
              <span className="nx-card-kicker">DATA &amp; SYSTEM STATUS</span>
              <button
                type="button"
                className="nx-link-btn"
                onClick={() => void refreshBackendStatus()}
                disabled={backendStatus.checking}
              >
                {backendStatus.checking ? "Checking..." : "Re-check API"}
              </button>
            </div>
            <h2 className="nx-card-title">
              {backendStatus.dbReady
                ? "PostGIS Spatial Backend Ready"
                : "Offline Deterministic Demo Ready"}
            </h2>
            <p className="nx-card-body">{backendStatus.detail}</p>

            <ul className="nx-status-list">
              <li>
                <span
                  className={
                    "nx-dot " + (backendStatus.dbReady ? "ok" : "amber")
                  }
                />
                <span>
                  <strong>Routing Engine:</strong>{" "}
                  {dataMode === "live"
                    ? "FastAPI + NetworkX Dijkstra (EPSG:32643)"
                    : "Client-side Topological Dijkstra (Binary Heap)"}
                </span>
              </li>
              <li>
                <span className="nx-dot ok" />
                <span>
                  <strong>Road Provenance:</strong> {activeArea.provenance}
                </span>
              </li>
              <li>
                <span
                  className={"nx-dot " + (mapError ? "err" : mapReady ? "ok" : "amber")}
                />
                <span>
                  <strong>Cesium 3D Globe:</strong>{" "}
                  {mapError
                    ? "Unavailable (2D/tabular workflow active)"
                    : mapReady
                    ? "WebGL 3D Viewer Ready"
                    : "Ready on Workspace Entry"}
                </span>
              </li>
            </ul>
          </div>
        </section>

        {/* Sample & Configured Scenarios */}
        <section className="nx-overview-section" aria-label="Sample Disaster Scenarios">
          <div className="nx-section-head">
            <div>
              <h2 className="nx-section-title">
                Preconfigured &amp; Saved Simulation Scenarios
              </h2>
              <p className="nx-section-sub">
                Select a deterministic scenario to inspect affected segments and
                compare baseline versus hazard-aware routes on the 3D map. All
                scenarios below represent simulated hazards, never live
                emergencies.
              </p>
            </div>
          </div>

          <div className="nx-scenario-grid">
            {scenarios.map((sc) => {
              const isSelected = sc.id === activeScenarioId;
              const area = STUDY_AREAS[sc.studyAreaId];
              return (
                <div
                  key={sc.id}
                  className={"nx-scenario-card" + (isSelected ? " selected" : "")}
                >
                  <div className="nx-scenario-top">
                    <span className={"nx-hazard-tag type-" + sc.type}>
                      {sc.type.replace("_", " ").toUpperCase()}
                    </span>
                    <span className="nx-scenario-area">{area.shortName}</span>
                  </div>
                  <h3 className="nx-scenario-name">{sc.name}</h3>
                  <p className="nx-scenario-desc">{sc.description}</p>
                  <div className="nx-scenario-meta mono">
                    <span>
                      {!sc.active
                        ? "Hazard Inactive"
                        : sc.severityMode === "closed"
                        ? "Rule: Impassable"
                        : `Rule: ${sc.penaltyMultiplier.toFixed(1)}× Penalty`}
                    </span>
                    <span>·</span>
                    <span>
                      {sc.geometryKind === "polygon"
                        ? `${sc.polygon.length}-pt Polygon`
                        : sc.geometryKind === "circle"
                        ? `${sc.radiusM} m Radius`
                        : `${sc.affectedRoadIds.length} Road ID(s)`}
                    </span>
                  </div>
                  <div className="nx-scenario-actions">
                    <button
                      type="button"
                      className="nx-btn nx-btn-secondary nx-btn-sm"
                      onClick={() => {
                        selectScenario(sc.id);
                        if (sc.studyAreaId !== studyAreaId) {
                          void loadStudyArea(sc.studyAreaId);
                        }
                        enterMapWorkspace();
                      }}
                    >
                      Configure in Map
                    </button>
                    <button
                      type="button"
                      className="nx-btn nx-btn-primary nx-btn-sm"
                      onClick={() => void handleQuickRunScenario(sc.id)}
                    >
                      Run Comparison →
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* Recent Session Runs (Rendered ONLY when actual runs exist in state) */}
        {recentRuns.length > 0 && (
          <section className="nx-overview-section" aria-label="Recent Route Runs">
            <h2 className="nx-section-title">Recent Session Route Analyses</h2>
            <div className="nx-recent-table-wrap">
              <table className="nx-table">
                <thead>
                  <tr>
                    <th>Scenario</th>
                    <th>Data Mode</th>
                    <th>Baseline</th>
                    <th>Hazard-Aware Alternative</th>
                    <th>Exposure Change</th>
                  </tr>
                </thead>
                <tbody>
                  {recentRuns.map((run, idx) => (
                    <tr key={`${run.provenance.computedAtIso}_${idx}`}>
                      <td>{run.scenarioUsed.name}</td>
                      <td className="mono">
                        {run.provenance.dataMode.toUpperCase()}
                      </td>
                      <td className="mono">
                        {run.baselineRoute.distanceM !== null
                          ? `${(run.baselineRoute.distanceM / 1000).toFixed(2)} km`
                          : "Unreachable"}
                      </td>
                      <td className="mono">
                        {run.hazardAwareRoute.feasible &&
                        run.hazardAwareRoute.distanceM !== null
                          ? `${(run.hazardAwareRoute.distanceM / 1000).toFixed(2)} km`
                          : "No feasible route"}
                      </td>
                      <td className="mono">
                        {Math.round(run.baselineRoute.exposedDistanceM)} m →{" "}
                        {run.hazardAwareRoute.feasible
                          ? `${Math.round(run.hazardAwareRoute.exposedDistanceM)} m`
                          : "N/A"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
