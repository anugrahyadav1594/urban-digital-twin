"use client";

import React, { useMemo, useState } from "react";
import { mapBridge } from "@/cesium/map-bridge";
import { STUDY_AREAS } from "@/lib/routing-engine";
import { useRouteAnalysisStore } from "@/stores/route-analysis-store";
import type {
  HazardSeverityMode,
  ScenarioHazardType,
  StudyAreaId,
  WizardStepNumber,
} from "@/types";

const STEP_META: { step: WizardStepNumber; short: string; title: string }[] = [
  { step: 1, short: "1 Area", title: "Step 1 — Set Study Area" },
  { step: 2, short: "2 Points", title: "Step 2 — Select Origin & Destination" },
  { step: 3, short: "3 Scenario", title: "Step 3 — Configure Simulated Disaster" },
  { step: 4, short: "4 Affected", title: "Step 4 — Review Affected Roads" },
  { step: 5, short: "5 Run", title: "Step 5 — Run Route Analysis" },
  { step: 6, short: "6 Routes", title: "Step 6 — Review Baseline & Alternative" },
  { step: 7, short: "7 Limits", title: "Step 7 — Compare & Inspect Limitations" },
];

export default function RouteWorkflowPanel() {
  const {
    leftPanelOpen,
    setLeftPanelOpen,
    setRightPanelOpen,
    wizardStep,
    setWizardStep,
    dataMode,
    setDataMode,
    backendStatus,
    studyAreaId,
    datasets,
    datasetLoading,
    datasetError,
    loadStudyArea,
    origin,
    destination,
    setOrigin,
    setDestination,
    swapWaypoints,
    clearWaypoints,
    scenarios,
    activeScenarioId,
    draftScenario,
    scenarioDirty,
    selectScenario,
    updateDraftScenario,
    saveScenario,
    cancelScenarioEdits,
    toggleRoadInScenario,
    interactionMode,
    setInteractionMode,
    drawingVertices,
    undoDrawingVertex,
    clearDrawingVertices,
    finishDrawingPolygon,
    costMetric,
    setCostMetric,
    affectedPreview,
    scenarioValidationError,
    analysisStatus,
    analysisError,
    result,
    runRouteAnalysis,
    getReadinessValidation,
    isResultStale,
  } = useRouteAnalysisStore();

  const [landmarkFilter, setLandmarkFilter] = useState("");
  const [roadFilter, setRoadFilter] = useState("");
  const [drawError, setDrawError] = useState<string | null>(null);
  const [manualOrigLon, setManualOrigLon] = useState("");
  const [manualOrigLat, setManualOrigLat] = useState("");
  const [manualDestLon, setManualDestLon] = useState("");
  const [manualDestLat, setManualDestLat] = useState("");

  const activeArea = STUDY_AREAS[studyAreaId];
  const activeDataset = datasets[studyAreaId];
  const readiness = getReadinessValidation();
  const stale = isResultStale();

  const areaScenarios = useMemo(
    () => scenarios.filter((sc) => sc.studyAreaId === studyAreaId),
    [scenarios, studyAreaId]
  );

  const filteredLandmarks = useMemo(() => {
    const list = activeDataset?.landmarks ?? [];
    const q = landmarkFilter.trim().toLowerCase();
    if (!q) return list.slice(0, 14);
    return list
      .filter(
        (lm) =>
          lm.name.toLowerCase().includes(q) ||
          lm.category.toLowerCase().includes(q)
      )
      .slice(0, 16);
  }, [activeDataset, landmarkFilter]);

  const selectableRoads = useMemo(() => {
    const roads = activeDataset?.roads ?? [];
    const q = roadFilter.trim().toLowerCase();
    const list = q
      ? roads.filter(
          (r) =>
            r.name.toLowerCase().includes(q) ||
            r.roadClass.toLowerCase().includes(q) ||
            r.id.toLowerCase().includes(q)
        )
      : roads.filter(
          (r) =>
            r.bridge ||
            r.roadClass === "primary" ||
            r.roadClass === "secondary" ||
            r.roadClass === "tertiary" ||
            r.roadClass === "arterial"
        );
    return list.slice(0, 18);
  }, [activeDataset, roadFilter]);

  if (!leftPanelOpen) {
    return (
      <button
        type="button"
        className="nx-drawer-toggle nx-drawer-toggle-left"
        onClick={() => setLeftPanelOpen(true)}
        aria-label="Open Route Analysis Workflow Panel"
      >
        <span>Workflow ({wizardStep}/7)</span>
        <span aria-hidden="true">▸</span>
      </button>
    );
  }

  const handleApplyManualOrigin = () => {
    const lon = Number(manualOrigLon);
    const lat = Number(manualOrigLat);
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) return;
    setOrigin({
      lon,
      lat,
      label: `Coord (${lat.toFixed(4)}°N, ${lon.toFixed(4)}°E)`,
      source: "coordinates",
    });
  };

  const handleApplyManualDest = () => {
    const lon = Number(manualDestLon);
    const lat = Number(manualDestLat);
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) return;
    setDestination({
      lon,
      lat,
      label: `Coord (${lat.toFixed(4)}°N, ${lon.toFixed(4)}°E)`,
      source: "coordinates",
    });
  };

  const handleFinishPolygon = () => {
    const res = finishDrawingPolygon();
    if (!res.ok) {
      setDrawError(res.error ?? "Polygon requires at least 3 valid vertices.");
    } else {
      setDrawError(null);
    }
  };

  return (
    <aside
      className="nx-side-panel nx-left-panel"
      aria-label="Disaster-Aware Route Analysis Workflow"
    >
      {/* Panel Header */}
      <div className="nx-panel-header">
        <div>
          <div className="nx-panel-kicker">GUIDED ROUTE WORKFLOW</div>
          <div className="nx-panel-title">Disaster-Aware Routing</div>
        </div>
        <button
          type="button"
          className="nx-icon-close"
          onClick={() => setLeftPanelOpen(false)}
          title="Collapse workflow panel"
          aria-label="Collapse workflow panel"
        >
          ◂
        </button>
      </div>

      {/* 7-Step Stepper */}
      <nav className="nx-stepper" aria-label="Route Analysis Steps">
        {STEP_META.map((item) => {
          const isCurrent = wizardStep === item.step;
          const isDone =
            (item.step === 1 && Boolean(activeDataset)) ||
            (item.step === 2 && Boolean(origin && destination)) ||
            (item.step === 3 && !scenarioValidationError) ||
            (item.step === 4 && Boolean(affectedPreview)) ||
            ((item.step === 5 || item.step === 6 || item.step === 7) &&
              Boolean(result) &&
              !stale);

          return (
            <button
              key={item.step}
              type="button"
              className={
                "nx-step-btn" +
                (isCurrent ? " current" : "") +
                (isDone ? " done" : "")
              }
              onClick={() => setWizardStep(item.step)}
              title={item.title}
              aria-current={isCurrent ? "step" : undefined}
            >
              <span className="nx-step-num">{item.step}</span>
              <span className="nx-step-txt">{item.short.slice(2)}</span>
            </button>
          );
        })}
      </nav>

      {/* Active Map Interaction Banner */}
      {interactionMode !== "navigate" && (
        <div className="nx-interaction-banner" role="status">
          <div className="nx-interaction-text">
            {interactionMode === "pick_origin" &&
              "Click on the 3D map to place Origin (A)."}
            {interactionMode === "pick_destination" &&
              "Click on the 3D map to place Destination (B)."}
            {interactionMode === "pick_hazard_center" &&
              "Click on the 3D map to set the circular hazard center."}
            {interactionMode === "toggle_road_segment" &&
              "Click road lines on the 3D map to toggle affected status."}
            {interactionMode === "draw_hazard_polygon" &&
              `Click map to add polygon vertices (${drawingVertices.length} placed, min 3).`}
          </div>

          <div className="nx-interaction-actions">
            {interactionMode === "draw_hazard_polygon" && (
              <>
                <button
                  type="button"
                  className="nx-btn nx-btn-primary nx-btn-xs"
                  disabled={drawingVertices.length < 3}
                  onClick={handleFinishPolygon}
                >
                  Finish ({drawingVertices.length})
                </button>
                <button
                  type="button"
                  className="nx-btn nx-btn-ghost nx-btn-xs"
                  disabled={drawingVertices.length === 0}
                  onClick={undoDrawingVertex}
                >
                  Undo
                </button>
                <button
                  type="button"
                  className="nx-btn nx-btn-ghost nx-btn-xs"
                  disabled={drawingVertices.length === 0}
                  onClick={clearDrawingVertices}
                >
                  Clear
                </button>
              </>
            )}
            <button
              type="button"
              className="nx-btn nx-btn-secondary nx-btn-xs"
              onClick={() => {
                setDrawError(null);
                setInteractionMode("navigate");
              }}
            >
              Done / Cancel
            </button>
          </div>
          {drawError && <div className="nx-inline-error">{drawError}</div>}
        </div>
      )}

      {/* Scrollable Step Body */}
      <div className="nx-panel-body">
        <div className="nx-step-heading">
          {STEP_META.find((m) => m.step === wizardStep)?.title}
        </div>

        {/* ───────── STEP 1: STUDY AREA ───────── */}
        {wizardStep === 1 && (
          <div className="nx-step-content">
            <p className="nx-help-text">
              Choose the geographic study area and inspect the underlying road
              graph before placing waypoints.
            </p>

            {(Object.keys(STUDY_AREAS) as StudyAreaId[]).map((id) => {
              const area = STUDY_AREAS[id];
              const selected = id === studyAreaId;
              return (
                <button
                  key={id}
                  type="button"
                  className={"nx-area-card" + (selected ? " active" : "")}
                  onClick={() => void loadStudyArea(id)}
                >
                  <div className="nx-area-card-top">
                    <strong>{area.name}</strong>
                    <span className="nx-mini-tag">
                      {area.isSyntheticBenchmark ? "SYNTHETIC" : "REAL OSM"}
                    </span>
                  </div>
                  <div className="nx-area-card-sub">{area.region}</div>
                  <div className="nx-area-card-desc">{area.provenance}</div>
                </button>
              );
            })}

            {datasetLoading && (
              <div className="nx-info-box">Loading road network topology...</div>
            )}
            {datasetError && (
              <div className="nx-error-box" role="alert">
                {datasetError}
              </div>
            )}
            {activeDataset && !datasetLoading && (
              <div className="nx-kv-box">
                <div className="nx-kv-row">
                  <span>Connected Intersections</span>
                  <strong className="mono">
                    {activeDataset.nodeCount.toLocaleString()}
                  </strong>
                </div>
                <div className="nx-kv-row">
                  <span>Directed Graph Edges</span>
                  <strong className="mono">
                    {activeDataset.directedEdgeCount.toLocaleString()}
                  </strong>
                </div>
                <div className="nx-kv-row">
                  <span>Named Landmarks / Facilities</span>
                  <strong className="mono">
                    {activeDataset.landmarks.length}
                  </strong>
                </div>
              </div>
            )}

            <div className="nx-step-nav-row">
              <button
                type="button"
                className="nx-btn nx-btn-ghost nx-btn-sm"
                onClick={() =>
                  mapBridge.flyToCoordinate(
                    activeArea.center.lon,
                    activeArea.center.lat,
                    activeArea.cameraHeightM
                  )
                }
              >
                Center Camera on Area
              </button>
              <button
                type="button"
                className="nx-btn nx-btn-primary nx-btn-sm"
                onClick={() => setWizardStep(2)}
              >
                Next: Waypoints →
              </button>
            </div>
          </div>
        )}

        {/* ───────── STEP 2: ORIGIN & DESTINATION ───────── */}
        {wizardStep === 2 && (
          <div className="nx-step-content">
            <p className="nx-help-text">
              Set Origin (A) and Destination (B) by clicking on the 3D map,
              selecting a named landmark, or entering coordinates.
            </p>

            {/* Origin Card */}
            <div className="nx-waypoint-box origin">
              <div className="nx-waypoint-head">
                <span className="nx-wp-badge origin">A · ORIGIN</span>
                <div style={{ display: "flex", gap: 6 }}>
                  <button
                    type="button"
                    className={
                      "nx-btn nx-btn-xs " +
                      (interactionMode === "pick_origin"
                        ? "nx-btn-primary"
                        : "nx-btn-secondary")
                    }
                    onClick={() =>
                      setInteractionMode(
                        interactionMode === "pick_origin"
                          ? "navigate"
                          : "pick_origin"
                      )
                    }
                  >
                    {interactionMode === "pick_origin"
                      ? "Clicking Map..."
                      : "Pick on Map"}
                  </button>
                  {origin && (
                    <button
                      type="button"
                      className="nx-btn nx-btn-ghost nx-btn-xs"
                      onClick={() =>
                        mapBridge.flyToCoordinate(origin.lon, origin.lat, 1600)
                      }
                      title="Zoom to Origin"
                    >
                      Zoom
                    </button>
                  )}
                </div>
              </div>
              {origin ? (
                <div className="nx-wp-details">
                  <div className="nx-wp-label">{origin.label}</div>
                  <div className="nx-wp-coords mono">
                    {origin.lat.toFixed(5)}°N, {origin.lon.toFixed(5)}°E
                  </div>
                </div>
              ) : (
                <div className="nx-wp-empty">No origin selected yet.</div>
              )}
            </div>

            {/* Destination Card */}
            <div className="nx-waypoint-box dest">
              <div className="nx-waypoint-head">
                <span className="nx-wp-badge dest">B · DESTINATION</span>
                <div style={{ display: "flex", gap: 6 }}>
                  <button
                    type="button"
                    className={
                      "nx-btn nx-btn-xs " +
                      (interactionMode === "pick_destination"
                        ? "nx-btn-primary"
                        : "nx-btn-secondary")
                    }
                    onClick={() =>
                      setInteractionMode(
                        interactionMode === "pick_destination"
                          ? "navigate"
                          : "pick_destination"
                      )
                    }
                  >
                    {interactionMode === "pick_destination"
                      ? "Clicking Map..."
                      : "Pick on Map"}
                  </button>
                  {destination && (
                    <button
                      type="button"
                      className="nx-btn nx-btn-ghost nx-btn-xs"
                      onClick={() =>
                        mapBridge.flyToCoordinate(
                          destination.lon,
                          destination.lat,
                          1600
                        )
                      }
                      title="Zoom to Destination"
                    >
                      Zoom
                    </button>
                  )}
                </div>
              </div>
              {destination ? (
                <div className="nx-wp-details">
                  <div className="nx-wp-label">{destination.label}</div>
                  <div className="nx-wp-coords mono">
                    {destination.lat.toFixed(5)}°N, {destination.lon.toFixed(5)}°E
                  </div>
                </div>
              ) : (
                <div className="nx-wp-empty">No destination selected yet.</div>
              )}
            </div>

            <div style={{ display: "flex", gap: 8 }}>
              <button
                type="button"
                className="nx-btn nx-btn-ghost nx-btn-xs"
                onClick={swapWaypoints}
                disabled={!origin && !destination}
              >
                ⇅ Swap A ↔ B
              </button>
              <button
                type="button"
                className="nx-btn nx-btn-ghost nx-btn-xs"
                onClick={clearWaypoints}
                disabled={!origin && !destination}
              >
                Clear Both
              </button>
              <button
                type="button"
                className="nx-btn nx-btn-ghost nx-btn-xs"
                onClick={() => {
                  setOrigin({ ...activeArea.defaultOrigin });
                  setDestination({ ...activeArea.defaultDestination });
                }}
              >
                Restore Defaults
              </button>
            </div>

            {/* Named Landmarks / Facilities Quick Picker */}
            <div className="nx-subcard">
              <label className="nx-label" htmlFor="nx-landmark-search">
                Search Landmarks, Bridges &amp; Facilities
              </label>
              <input
                id="nx-landmark-search"
                type="text"
                className="nx-input"
                placeholder="Filter by name (e.g., Fire Brigade, Life Care, Adai, Bridge)..."
                value={landmarkFilter}
                onChange={(e) => setLandmarkFilter(e.target.value)}
              />
              <div className="nx-landmark-list">
                {filteredLandmarks.map((lm) => (
                  <div key={lm.id} className="nx-landmark-row">
                    <div className="nx-landmark-info">
                      <div className="nx-landmark-name">{lm.name}</div>
                      <div className="nx-landmark-cat mono">
                        {lm.category} · {lm.lat.toFixed(4)}°N, {lm.lon.toFixed(4)}°E
                      </div>
                    </div>
                    <div className="nx-landmark-btns">
                      <button
                        type="button"
                        className="nx-mini-action orig"
                        onClick={() =>
                          setOrigin({
                            lon: lm.lon,
                            lat: lm.lat,
                            label: lm.name,
                            source: "landmark",
                          })
                        }
                        title={`Set ${lm.name} as Origin`}
                      >
                        Set A
                      </button>
                      <button
                        type="button"
                        className="nx-mini-action dest"
                        onClick={() =>
                          setDestination({
                            lon: lm.lon,
                            lat: lm.lat,
                            label: lm.name,
                            source: "landmark",
                          })
                        }
                        title={`Set ${lm.name} as Destination`}
                      >
                        Set B
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Direct Coordinate Entry */}
            <details className="nx-details">
              <summary>Enter Coordinates Manually (Lon / Lat)</summary>
              <div className="nx-coord-grid">
                <div className="nx-coord-row">
                  <input
                    type="number"
                    step="0.0001"
                    className="nx-input"
                    placeholder="Origin Lon (73.12)"
                    aria-label="Origin Longitude"
                    value={manualOrigLon}
                    onChange={(e) => setManualOrigLon(e.target.value)}
                  />
                  <input
                    type="number"
                    step="0.0001"
                    className="nx-input"
                    placeholder="Origin Lat (18.99)"
                    aria-label="Origin Latitude"
                    value={manualOrigLat}
                    onChange={(e) => setManualOrigLat(e.target.value)}
                  />
                  <button
                    type="button"
                    className="nx-btn nx-btn-secondary nx-btn-xs"
                    onClick={handleApplyManualOrigin}
                  >
                    Set A
                  </button>
                </div>
                <div className="nx-coord-row">
                  <input
                    type="number"
                    step="0.0001"
                    className="nx-input"
                    placeholder="Dest Lon (73.13)"
                    aria-label="Destination Longitude"
                    value={manualDestLon}
                    onChange={(e) => setManualDestLon(e.target.value)}
                  />
                  <input
                    type="number"
                    step="0.0001"
                    className="nx-input"
                    placeholder="Dest Lat (18.98)"
                    aria-label="Destination Latitude"
                    value={manualDestLat}
                    onChange={(e) => setManualDestLat(e.target.value)}
                  />
                  <button
                    type="button"
                    className="nx-btn nx-btn-secondary nx-btn-xs"
                    onClick={handleApplyManualDest}
                  >
                    Set B
                  </button>
                </div>
              </div>
            </details>

            <div className="nx-step-nav-row">
              <button
                type="button"
                className="nx-btn nx-btn-ghost nx-btn-sm"
                onClick={() => setWizardStep(1)}
              >
                ← Back
              </button>
              <button
                type="button"
                className="nx-btn nx-btn-primary nx-btn-sm"
                onClick={() => setWizardStep(3)}
              >
                Next: Scenario →
              </button>
            </div>
          </div>
        )}

        {/* ───────── STEP 3: SCENARIO BUILDER ───────── */}
        {wizardStep === 3 && (
          <div className="nx-step-content">
            <div className="nx-sim-disclosure">
              <strong>SIMULATED SCENARIO:</strong> Hazards configured here are
              deterministic research overlays, never live emergency feeds.
            </div>

            <label className="nx-label" htmlFor="nx-preset-select">
              Load Preset or Saved Scenario
            </label>
            <select
              id="nx-preset-select"
              className="nx-select"
              value={activeScenarioId}
              onChange={(e) => selectScenario(e.target.value)}
            >
              {areaScenarios.map((sc) => (
                <option key={sc.id} value={sc.id}>
                  {sc.isPreset ? "[Preset] " : "[Saved] "}
                  {sc.name}
                </option>
              ))}
            </select>

            <div className="nx-form-group">
              <div className="nx-row-between">
                <label className="nx-label" htmlFor="nx-scen-name">
                  Scenario Name
                </label>
                <label className="nx-toggle-label">
                  <input
                    type="checkbox"
                    checked={draftScenario.active}
                    onChange={(e) =>
                      updateDraftScenario({ active: e.target.checked })
                    }
                  />
                  <span>{draftScenario.active ? "Active" : "Inactive"}</span>
                </label>
              </div>
              <input
                id="nx-scen-name"
                type="text"
                className="nx-input"
                value={draftScenario.name}
                onChange={(e) => updateDraftScenario({ name: e.target.value })}
              />
            </div>

            {/* Disaster Type */}
            <div className="nx-form-group">
              <span className="nx-label">Simulated Disaster Type</span>
              <div className="nx-segmented">
                {(
                  [
                    ["flood", "Flood"],
                    ["fire", "Fire"],
                    ["road_blockage", "Blockage"],
                    ["affected_zone", "Zone"],
                  ] as [ScenarioHazardType, string][]
                ).map(([val, label]) => (
                  <button
                    key={val}
                    type="button"
                    className={
                      "nx-seg-btn" + (draftScenario.type === val ? " active" : "")
                    }
                    onClick={() => updateDraftScenario({ type: val })}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {/* Severity / Graph Cost Model */}
            <div className="nx-form-group">
              <span className="nx-label">Edge Cost / Passability Rule</span>
              <div className="nx-segmented">
                {(
                  [
                    ["closed", "Impassable (Close Edges)"],
                    ["penalized", "Cost Penalty Multiplier"],
                  ] as [HazardSeverityMode, string][]
                ).map(([val, label]) => (
                  <button
                    key={val}
                    type="button"
                    className={
                      "nx-seg-btn" +
                      (draftScenario.severityMode === val ? " active" : "")
                    }
                    onClick={() => updateDraftScenario({ severityMode: val })}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {draftScenario.severityMode === "penalized" && (
                <div className="nx-slider-box">
                  <div className="nx-row-between">
                    <label htmlFor="nx-penalty-range" className="nx-label-sm">
                      Traversal Cost Multiplier
                    </label>
                    <span className="mono" style={{ color: "#fbbf24" }}>
                      {draftScenario.penaltyMultiplier.toFixed(1)}×
                    </span>
                  </div>
                  <input
                    id="nx-penalty-range"
                    type="range"
                    min="1.2"
                    max="10"
                    step="0.2"
                    value={draftScenario.penaltyMultiplier}
                    onChange={(e) =>
                      updateDraftScenario({
                        penaltyMultiplier: Number(e.target.value),
                      })
                    }
                  />
                  <div className="nx-micro-note">
                    Multiplies affected edge travel cost by{" "}
                    {draftScenario.penaltyMultiplier.toFixed(1)}×; detours are
                    chosen when detour cost is lower than penalized traversal.
                  </div>
                </div>
              )}
            </div>

            {/* Geography Mode */}
            <div className="nx-form-group">
              <span className="nx-label">Affected Footprint Geometry</span>
              <div className="nx-segmented">
                <button
                  type="button"
                  className={
                    "nx-seg-btn" +
                    (draftScenario.geometryKind === "polygon" ? " active" : "")
                  }
                  onClick={() =>
                    updateDraftScenario({ geometryKind: "polygon" })
                  }
                >
                  Polygon
                </button>
                <button
                  type="button"
                  className={
                    "nx-seg-btn" +
                    (draftScenario.geometryKind === "circle" ? " active" : "")
                  }
                  onClick={() => {
                    const fallbackCenter: [number, number] =
                      draftScenario.center ?? [
                        activeArea.center.lon,
                        activeArea.center.lat,
                      ];
                    updateDraftScenario({
                      geometryKind: "circle",
                      center: fallbackCenter,
                    });
                  }}
                >
                  Circle Zone
                </button>
                <button
                  type="button"
                  className={
                    "nx-seg-btn" +
                    (draftScenario.geometryKind === "segments_only"
                      ? " active"
                      : "")
                  }
                  onClick={() =>
                    updateDraftScenario({ geometryKind: "segments_only" })
                  }
                >
                  Road List
                </button>
              </div>

              {draftScenario.geometryKind === "polygon" && (
                <div className="nx-subcard">
                  <div className="nx-row-between">
                    <span className="mono" style={{ fontSize: 11.5 }}>
                      Vertices: {draftScenario.polygon.length}
                    </span>
                    <button
                      type="button"
                      className="nx-btn nx-btn-secondary nx-btn-xs"
                      onClick={() => {
                        setDrawError(null);
                        setInteractionMode("draw_hazard_polygon");
                      }}
                    >
                      ✎ Draw Polygon on 3D Map
                    </button>
                  </div>
                </div>
              )}

              {draftScenario.geometryKind === "circle" && (
                <div className="nx-subcard">
                  <div className="nx-row-between" style={{ marginBottom: 8 }}>
                    <span className="mono" style={{ fontSize: 11.5 }}>
                      Center:{" "}
                      {draftScenario.center
                        ? `${draftScenario.center[1].toFixed(4)}°N, ${draftScenario.center[0].toFixed(4)}°E`
                        : "Not set"}
                    </span>
                    <button
                      type="button"
                      className="nx-btn nx-btn-secondary nx-btn-xs"
                      onClick={() => setInteractionMode("pick_hazard_center")}
                    >
                      Pick Center on Map
                    </button>
                  </div>
                  <div className="nx-row-between">
                    <label htmlFor="nx-radius-slider" className="nx-label-sm">
                      Hazard Radius
                    </label>
                    <span className="mono">{draftScenario.radiusM} m</span>
                  </div>
                  <input
                    id="nx-radius-slider"
                    type="range"
                    min="60"
                    max="1500"
                    step="20"
                    value={draftScenario.radiusM}
                    onChange={(e) =>
                      updateDraftScenario({ radiusM: Number(e.target.value) })
                    }
                  />
                </div>
              )}

              {/* Explicit Road Segment Picker (works alongside any geometry mode) */}
              <div className="nx-subcard" style={{ marginTop: 8 }}>
                <div className="nx-row-between" style={{ marginBottom: 6 }}>
                  <span className="nx-label-sm">
                    Explicit Affected Road Segments (
                    {draftScenario.affectedRoadIds.length})
                  </span>
                  <button
                    type="button"
                    className={
                      "nx-btn nx-btn-xs " +
                      (interactionMode === "toggle_road_segment"
                        ? "nx-btn-primary"
                        : "nx-btn-ghost")
                    }
                    onClick={() =>
                      setInteractionMode(
                        interactionMode === "toggle_road_segment"
                          ? "navigate"
                          : "toggle_road_segment"
                      )
                    }
                  >
                    {interactionMode === "toggle_road_segment"
                      ? "Done Clicking Roads"
                      : "Click Roads on Map"}
                  </button>
                </div>
                <input
                  type="text"
                  className="nx-input"
                  placeholder="Filter streets/bridges (e.g., Sukapur, Matheran, Bridge)..."
                  value={roadFilter}
                  onChange={(e) => setRoadFilter(e.target.value)}
                />
                <div className="nx-road-checklist">
                  {selectableRoads.map((r) => {
                    const checked = draftScenario.affectedRoadIds.includes(r.id);
                    return (
                      <label key={r.id} className="nx-road-check-item">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleRoadInScenario(r.id)}
                        />
                        <span className="nx-road-check-name">{r.name}</span>
                        <span className="nx-road-check-cls mono">
                          {r.roadClass}
                        </span>
                      </label>
                    );
                  })}
                </div>
              </div>
            </div>

            {scenarioValidationError && (
              <div className="nx-error-box" role="alert">
                {scenarioValidationError}
              </div>
            )}

            {/* Save / Cancel Scenario Actions */}
            <div className="nx-scenario-save-bar">
              <button
                type="button"
                className="nx-btn nx-btn-secondary nx-btn-xs"
                onClick={() => saveScenario(false)}
                disabled={Boolean(scenarioValidationError)}
              >
                {draftScenario.isPreset ? "Save as Custom" : "Save Scenario"}
              </button>
              <button
                type="button"
                className="nx-btn nx-btn-ghost nx-btn-xs"
                onClick={cancelScenarioEdits}
                disabled={!scenarioDirty}
              >
                Revert Edits
              </button>
            </div>

            <div className="nx-step-nav-row">
              <button
                type="button"
                className="nx-btn nx-btn-ghost nx-btn-sm"
                onClick={() => setWizardStep(2)}
              >
                ← Back
              </button>
              <button
                type="button"
                className="nx-btn nx-btn-primary nx-btn-sm"
                onClick={() => setWizardStep(4)}
              >
                Next: Affected Roads →
              </button>
            </div>
          </div>
        )}

        {/* ───────── STEP 4: REVIEW AFFECTED ROADS ───────── */}
        {wizardStep === 4 && (
          <div className="nx-step-content">
            <p className="nx-help-text">
              Inspect the exact graph edges intersected by{" "}
              <strong>{draftScenario.name}</strong> before computing routes.
            </p>

            {affectedPreview ? (
              <>
                <div className="nx-kv-box">
                  <div className="nx-kv-row">
                    <span>Scenario State</span>
                    <strong
                      style={{
                        color: draftScenario.active ? "#fca5a5" : "#94a3b8",
                      }}
                    >
                      {draftScenario.active ? "Active Simulation" : "Inactive"}
                    </strong>
                  </div>
                  <div className="nx-kv-row">
                    <span>Impassable Directed Edges</span>
                    <strong className="mono" style={{ color: "#f87171" }}>
                      {affectedPreview.closedEdgeCount}
                    </strong>
                  </div>
                  <div className="nx-kv-row">
                    <span>Penalized Directed Edges</span>
                    <strong className="mono" style={{ color: "#fbbf24" }}>
                      {affectedPreview.penalizedEdgeCount}
                    </strong>
                  </div>
                  <div className="nx-kv-row">
                    <span>Affected Corridor Length</span>
                    <strong className="mono">
                      {affectedPreview.closedLengthM +
                        affectedPreview.penalizedLengthM}{" "}
                      m
                    </strong>
                  </div>
                </div>

                {draftScenario.active &&
                  affectedPreview.closedEdgeCount +
                    affectedPreview.penalizedEdgeCount ===
                    0 && (
                    <div className="nx-warn-box">
                      Zero road segments intersect this hazard configuration.
                      Baseline and hazard-aware routes will be identical.
                    </div>
                  )}

                {(affectedPreview.closedRoadNames.length > 0 ||
                  affectedPreview.penalizedRoadNames.length > 0) && (
                  <div className="nx-subcard">
                    <div className="nx-label-sm" style={{ marginBottom: 6 }}>
                      Affected Streets &amp; Bridges
                    </div>
                    <ul className="nx-affected-street-list">
                      {affectedPreview.closedRoadNames
                        .slice(0, 10)
                        .map((name) => (
                          <li key={`c_${name}`}>
                            <span className="nx-dot err" />
                            <span>{name}</span>
                            <span className="mono nx-tag-closed">CLOSED</span>
                          </li>
                        ))}
                      {affectedPreview.penalizedRoadNames
                        .slice(0, 10)
                        .map((name) => (
                          <li key={`p_${name}`}>
                            <span className="nx-dot amber" />
                            <span>{name}</span>
                            <span className="mono nx-tag-pen">
                              {draftScenario.penaltyMultiplier.toFixed(1)}×
                            </span>
                          </li>
                        ))}
                    </ul>
                  </div>
                )}
              </>
            ) : (
              <div className="nx-info-box">
                Configure a valid scenario in Step 3 to preview affected roads.
              </div>
            )}

            <div className="nx-step-nav-row">
              <button
                type="button"
                className="nx-btn nx-btn-ghost nx-btn-sm"
                onClick={() => setWizardStep(3)}
              >
                ← Edit Scenario
              </button>
              <button
                type="button"
                className="nx-btn nx-btn-primary nx-btn-sm"
                onClick={() => setWizardStep(5)}
              >
                Next: Run Analysis →
              </button>
            </div>
          </div>
        )}

        {/* ───────── STEP 5: RUN ROUTE ANALYSIS ───────── */}
        {wizardStep === 5 && (
          <div className="nx-step-content">
            <p className="nx-help-text">
              Choose the optimization objective and run Dijkstra&apos;s
              shortest-path comparison across identical baseline and
              hazard-modified networks.
            </p>

            {/* Optimization Metric */}
            <div className="nx-form-group">
              <span className="nx-label">Shortest-Path Cost Basis</span>
              <div className="nx-segmented">
                <button
                  type="button"
                  className={
                    "nx-seg-btn" + (costMetric === "time" ? " active" : "")
                  }
                  onClick={() => setCostMetric("time")}
                >
                  Nominal Travel Time
                </button>
                <button
                  type="button"
                  className={
                    "nx-seg-btn" + (costMetric === "distance" ? " active" : "")
                  }
                  onClick={() => setCostMetric("distance")}
                >
                  Shortest Distance (m)
                </button>
              </div>
            </div>

            {/* Data Execution Mode */}
            <div className="nx-form-group">
              <span className="nx-label">Execution &amp; Data Source Mode</span>
              <div className="nx-segmented">
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
                  disabled={activeArea.isSyntheticBenchmark}
                  title={
                    activeArea.isSyntheticBenchmark
                      ? "Synthetic Benchmark Grid is local-only"
                      : "Execute on FastAPI + PostGIS backend"
                  }
                  onClick={() => setDataMode("live")}
                >
                  Live PostGIS API
                </button>
              </div>
              {dataMode === "live" && !backendStatus.dbReady && (
                <div className="nx-warn-box" style={{ marginTop: 6 }}>
                  PostGIS backend currently reports offline ({backendStatus.detail}).
                  Live mode will attempt the real API and report any error
                  without silently substituting demo data.
                </div>
              )}
            </div>

            {/* Readiness Summary */}
            <div className="nx-kv-box">
              <div className="nx-kv-row">
                <span>Origin (A)</span>
                <strong className="mono">
                  {origin ? origin.label.slice(0, 22) : "Missing"}
                </strong>
              </div>
              <div className="nx-kv-row">
                <span>Destination (B)</span>
                <strong className="mono">
                  {destination ? destination.label.slice(0, 22) : "Missing"}
                </strong>
              </div>
              <div className="nx-kv-row">
                <span>Scenario</span>
                <strong>{draftScenario.name.slice(0, 24)}</strong>
              </div>
            </div>

            {!readiness.valid && (
              <div className="nx-error-box" role="alert">
                <strong>Required before running:</strong>
                <ul style={{ margin: "6px 0 0 16px", padding: 0 }}>
                  {readiness.reasons.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
              </div>
            )}

            {analysisError && (
              <div className="nx-error-box" role="alert">
                <div>{analysisError}</div>
                {dataMode === "live" && (
                  <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                    <button
                      type="button"
                      className="nx-btn nx-btn-secondary nx-btn-xs"
                      onClick={() => void runRouteAnalysis()}
                    >
                      Retry Live API
                    </button>
                    <button
                      type="button"
                      className="nx-btn nx-btn-primary nx-btn-xs"
                      onClick={() => {
                        setDataMode("demo");
                        setTimeout(() => {
                          void useRouteAnalysisStore
                            .getState()
                            .runRouteAnalysis();
                        }, 0);
                      }}
                    >
                      Switch to Demo Mode &amp; Run
                    </button>
                  </div>
                )}
              </div>
            )}

            <button
              type="button"
              className="nx-btn nx-btn-primary nx-btn-block"
              disabled={!readiness.valid || analysisStatus === "running"}
              onClick={() => void runRouteAnalysis()}
            >
              {analysisStatus === "running"
                ? "Computing Baseline & Hazard-Aware Routes..."
                : "Run Route Analysis"}
            </button>

            <div className="nx-step-nav-row">
              <button
                type="button"
                className="nx-btn nx-btn-ghost nx-btn-sm"
                onClick={() => setWizardStep(4)}
              >
                ← Back
              </button>
              {result && (
                <button
                  type="button"
                  className="nx-btn nx-btn-secondary nx-btn-sm"
                  onClick={() => {
                    setRightPanelOpen(true);
                    setWizardStep(6);
                  }}
                >
                  View Results →
                </button>
              )}
            </div>
          </div>
        )}

        {/* ───────── STEPS 6 & 7: ROUTE REVIEW & LIMITATIONS ───────── */}
        {(wizardStep === 6 || wizardStep === 7) && (
          <div className="nx-step-content">
            {!result ? (
              <div className="nx-info-box">
                No route comparison has been executed yet. Complete Step 5 to
                compute baseline and hazard-aware routes.
                <div style={{ marginTop: 10 }}>
                  <button
                    type="button"
                    className="nx-btn nx-btn-primary nx-btn-sm"
                    onClick={() => setWizardStep(5)}
                  >
                    Go to Step 5 — Run Analysis
                  </button>
                </div>
              </div>
            ) : (
              <>
                {stale && (
                  <div className="nx-warn-box" role="status">
                    <strong>Inputs Changed:</strong> Waypoints or scenario
                    settings were edited after this run. Re-run analysis to
                    update the map and metrics.
                    <div style={{ marginTop: 8 }}>
                      <button
                        type="button"
                        className="nx-btn nx-btn-primary nx-btn-xs"
                        onClick={() => void runRouteAnalysis()}
                      >
                        Re-run Updated Analysis
                      </button>
                    </div>
                  </div>
                )}

                <div className="nx-subcard">
                  <div className="nx-label-sm">Outcome Summary</div>
                  <p
                    style={{
                      fontSize: 12.5,
                      lineHeight: 1.55,
                      color: "#e2e8f0",
                      margin: "6px 0 0",
                    }}
                  >
                    {result.comparison.summary}
                  </p>
                </div>

                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <button
                    type="button"
                    className="nx-btn nx-btn-secondary nx-btn-xs"
                    onClick={() => mapBridge.fitToAnalysis()}
                  >
                    Fit Map to Routes
                  </button>
                  <button
                    type="button"
                    className="nx-btn nx-btn-primary nx-btn-xs"
                    onClick={() => setRightPanelOpen(true)}
                  >
                    Open Full Comparison Panel ▸
                  </button>
                </div>

                {wizardStep === 6 ? (
                  <div className="nx-step-nav-row">
                    <button
                      type="button"
                      className="nx-btn nx-btn-ghost nx-btn-sm"
                      onClick={() => setWizardStep(3)}
                    >
                      ← Modify Scenario
                    </button>
                    <button
                      type="button"
                      className="nx-btn nx-btn-primary nx-btn-sm"
                      onClick={() => {
                        setRightPanelOpen(true);
                        setWizardStep(7);
                      }}
                    >
                      Step 7: Limitations →
                    </button>
                  </div>
                ) : (
                  <div className="nx-step-nav-row">
                    <button
                      type="button"
                      className="nx-btn nx-btn-ghost nx-btn-sm"
                      onClick={() => setWizardStep(6)}
                    >
                      ← Step 6: Routes
                    </button>
                    <button
                      type="button"
                      className="nx-btn nx-btn-secondary nx-btn-sm"
                      onClick={() => setWizardStep(2)}
                    >
                      Edit Origin / Dest
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
