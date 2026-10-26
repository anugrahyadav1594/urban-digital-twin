"use client";

import React from "react";
import { mapBridge } from "@/cesium/map-bridge";
import { useRouteAnalysisStore } from "@/stores/route-analysis-store";

function formatDist(meters: number | null): string {
  if (meters === null || !Number.isFinite(meters)) return "Unreachable";
  if (meters >= 1000) return `${(meters / 1000).toFixed(2)} km`;
  return `${Math.round(meters)} m`;
}

function formatDuration(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds)) return "Unreachable";
  const mins = seconds / 60;
  if (mins >= 1) return `${mins.toFixed(1)} min`;
  return `${Math.round(seconds)} s`;
}

function formatSignedDelta(
  delta: number | null,
  unit: "km" | "min"
): string {
  if (delta === null || !Number.isFinite(delta)) return "N/A";
  const scaled = unit === "km" ? delta / 1000 : delta / 60;
  const sign = scaled > 0 ? "+" : "";
  return `${sign}${scaled.toFixed(2)} ${unit}`;
}

export default function RouteResultsPanel() {
  const {
    rightPanelOpen,
    setRightPanelOpen,
    result,
    analysisStatus,
    runRouteAnalysis,
    resetDemo,
    isResultStale,
  } = useRouteAnalysisStore();

  const stale = isResultStale();

  if (!rightPanelOpen) {
    return (
      <button
        type="button"
        className="nx-drawer-toggle nx-drawer-toggle-right"
        onClick={() => setRightPanelOpen(true)}
        aria-label="Open Route Comparison Results Panel"
      >
        <span aria-hidden="true">◂</span>
        <span>
          {result
            ? stale
              ? "Results (Outdated)"
              : "Results & Comparison"
            : "Comparison"}
        </span>
      </button>
    );
  }

  const base = result?.baselineRoute;
  const alt = result?.hazardAwareRoute;
  const comp = result?.comparison;
  const prov = result?.provenance;

  const maxDist = Math.max(
    1,
    base?.distanceM ?? 0,
    alt?.distanceM ?? 0
  );
  const maxExp = Math.max(
    1,
    base?.exposedDistanceM ?? 0,
    alt?.exposedDistanceM ?? 0
  );

  return (
    <aside
      className="nx-side-panel nx-right-panel"
      aria-label="Route Comparison and Limitations"
    >
      <div className="nx-panel-header">
        <div>
          <div className="nx-panel-kicker">ROUTE COMPARISON &amp; METRICS</div>
          <div className="nx-panel-title">Baseline vs Hazard-Aware</div>
        </div>
        <button
          type="button"
          className="nx-icon-close"
          onClick={() => setRightPanelOpen(false)}
          title="Collapse results panel"
          aria-label="Collapse results panel"
        >
          ▸
        </button>
      </div>

      <div className="nx-panel-body">
        {!result ? (
          <div className="nx-empty-results">
            <div className="nx-empty-title">No Route Analysis Computed Yet</div>
            <p className="nx-help-text">
              Configure Origin (A), Destination (B), and a simulated disaster
              scenario in the left panel, then click{" "}
              <strong>Run Route Analysis</strong> to compare baseline and
              hazard-aware routes.
            </p>
            <button
              type="button"
              className="nx-btn nx-btn-primary nx-btn-sm"
              disabled={analysisStatus === "running"}
              onClick={() => void runRouteAnalysis()}
            >
              {analysisStatus === "running"
                ? "Running Analysis..."
                : "Run Current Configuration"}
            </button>
          </div>
        ) : (
          <div className="nx-results-stack">
            {/* Provenance & Data Mode Header */}
            <div className="nx-prov-strip">
              <span
                className={
                  "nx-pill " +
                  (prov?.dataMode === "live" ? "nx-pill-live" : "nx-pill-demo")
                }
              >
                {prov?.dataMode === "live"
                  ? "LIVE POSTGIS RESULT"
                  : "DEMO / SIMULATED DATA"}
              </span>
              <span className="mono nx-prov-time">
                {result.computationTimeMs.toFixed(1)} ms ·{" "}
                {prov?.costMetric === "time" ? "Min Time" : "Min Distance"}
              </span>
            </div>

            {/* Stale Result Guard */}
            {stale && (
              <div className="nx-warn-box" role="status">
                <strong>Historical Result (Inputs Modified):</strong> This
                result reflects <em>{result.scenarioUsed.name}</em> prior to
                your latest edits.
                <div style={{ marginTop: 8 }}>
                  <button
                    type="button"
                    className="nx-btn nx-btn-primary nx-btn-xs"
                    disabled={analysisStatus === "running"}
                    onClick={() => void runRouteAnalysis()}
                  >
                    Re-run for Current Inputs
                  </button>
                </div>
              </div>
            )}

            {/* Feasibility Status Banner */}
            <div
              className={
                "nx-feasibility-banner " +
                (!alt?.feasible
                  ? "unreachable"
                  : comp?.routesIdentical
                  ? "identical"
                  : "detour")
              }
              role="status"
            >
              <div className="nx-feasibility-title">
                {!alt?.feasible
                  ? "No feasible route found under the current scenario"
                  : comp?.routesIdentical
                  ? "Route Feasibility: Feasible (Identical to Baseline)"
                  : "Route Feasibility: Feasible Detour Identified"}
              </div>
              <div className="nx-feasibility-sub">
                Scenario: <strong>{result.scenarioUsed.name}</strong>
              </div>
            </div>

            {/* Compact Metric Cards */}
            <div className="nx-metric-cards">
              <div className="nx-mcard">
                <div className="nx-mcard-label">Baseline Route</div>
                <div className="nx-mcard-val mono" style={{ color: "#7dd3fc" }}>
                  {formatDist(base?.distanceM ?? null)}
                </div>
                <div className="nx-mcard-sub mono">
                  {formatDuration(base?.travelTimeS ?? null)} nominal
                </div>
              </div>

              <div className="nx-mcard">
                <div className="nx-mcard-label">Hazard-Aware Alt</div>
                <div
                  className="nx-mcard-val mono"
                  style={{
                    color: alt?.feasible ? "#fdba74" : "#fca5a5",
                  }}
                >
                  {alt?.feasible
                    ? formatDist(alt.distanceM)
                    : "Unreachable"}
                </div>
                <div className="nx-mcard-sub mono">
                  {alt?.feasible
                    ? `${formatDuration(alt.travelTimeS)} nominal`
                    : "Graph disconnected"}
                </div>
              </div>

              <div className="nx-mcard">
                <div className="nx-mcard-label">Detour Trade-Off</div>
                <div className="nx-mcard-val mono">
                  {alt?.feasible
                    ? formatSignedDelta(comp?.distanceDeltaM ?? null, "km")
                    : "N/A"}
                </div>
                <div className="nx-mcard-sub mono">
                  {alt?.feasible
                    ? `${formatSignedDelta(
                        comp?.timeDeltaS ?? null,
                        "min"
                      )} (${
                        comp?.distanceDeltaPct !== null &&
                        comp?.distanceDeltaPct !== undefined
                          ? `${comp.distanceDeltaPct >= 0 ? "+" : ""}${comp.distanceDeltaPct}%`
                          : "0%"
                      })`
                    : "Destination isolated"}
                </div>
              </div>

              <div className="nx-mcard">
                <div className="nx-mcard-label">Simulated Exposure</div>
                <div className="nx-mcard-val mono">
                  {Math.round(base?.exposedDistanceM ?? 0)} m →{" "}
                  {alt?.feasible ? `${Math.round(alt.exposedDistanceM)} m` : "—"}
                </div>
                <div className="nx-mcard-sub mono">
                  {base?.affectedSegmentCount ?? 0} segs →{" "}
                  {alt?.feasible ? `${alt.affectedSegmentCount} segs` : "N/A"}
                </div>
              </div>
            </div>

            {/* Plain-English Explanation */}
            <div className="nx-subcard">
              <div className="nx-label-sm">Plain-English Route Comparison</div>
              <p className="nx-explanation-p">{comp?.summary}</p>
            </div>

            {/* Side-by-Side Comparison Table */}
            <div className="nx-table-card">
              <table className="nx-table nx-compare-table">
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th style={{ color: "#7dd3fc" }}>Baseline</th>
                    <th style={{ color: "#fdba74" }}>Hazard-Aware</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Route Feasibility</td>
                    <td className="mono">
                      {base?.feasible ? "Feasible" : "Unreachable"}
                    </td>
                    <td className="mono">
                      {alt?.feasible ? "Feasible" : "No feasible route"}
                    </td>
                  </tr>
                  <tr>
                    <td>Network Distance</td>
                    <td className="mono">{formatDist(base?.distanceM ?? null)}</td>
                    <td className="mono">
                      {alt?.feasible ? formatDist(alt.distanceM) : "—"}
                    </td>
                  </tr>
                  <tr>
                    <td>Nominal Travel Time</td>
                    <td className="mono">
                      {formatDuration(base?.travelTimeS ?? null)}
                    </td>
                    <td className="mono">
                      {alt?.feasible ? formatDuration(alt.travelTimeS) : "—"}
                    </td>
                  </tr>
                  <tr>
                    <td>Graph Edges Traversed</td>
                    <td className="mono">{base?.segmentCount ?? 0}</td>
                    <td className="mono">
                      {alt?.feasible ? alt.segmentCount : "—"}
                    </td>
                  </tr>
                  <tr>
                    <td>Affected Segments Hit</td>
                    <td className="mono">{base?.affectedSegmentCount ?? 0}</td>
                    <td className="mono">
                      {alt?.feasible ? alt.affectedSegmentCount : "—"}
                    </td>
                  </tr>
                  <tr>
                    <td>Simulated Exposure</td>
                    <td className="mono">
                      {Math.round(base?.exposedDistanceM ?? 0)} m
                    </td>
                    <td className="mono">
                      {alt?.feasible
                        ? `${Math.round(alt.exposedDistanceM)} m`
                        : "—"}
                    </td>
                  </tr>
                </tbody>
              </table>
              <div className="nx-micro-note" style={{ marginTop: 6 }}>
                Exposure formula: sum of geodesic lengths (m) of traversed
                directed road edges intersecting the active simulated hazard.
              </div>
            </div>

            {/* Real Computed Visual Comparison Bars (only when feasible data exists) */}
            {base?.feasible && base.distanceM !== null && (
              <div className="nx-subcard">
                <div className="nx-label-sm" style={{ marginBottom: 8 }}>
                  Measured Distance &amp; Simulated Exposure Comparison
                </div>

                <div className="nx-bar-group">
                  <div className="nx-bar-row-label">
                    <span>Baseline Distance</span>
                    <span className="mono">{formatDist(base.distanceM)}</span>
                  </div>
                  <div className="nx-bar-track">
                    <div
                      className="nx-bar-fill baseline"
                      style={{
                        width: `${Math.max(
                          4,
                          Math.round((base.distanceM / maxDist) * 100)
                        )}%`,
                      }}
                    />
                  </div>
                </div>

                {alt?.feasible && alt.distanceM !== null && (
                  <div className="nx-bar-group">
                    <div className="nx-bar-row-label">
                      <span>Hazard-Aware Distance</span>
                      <span className="mono">{formatDist(alt.distanceM)}</span>
                    </div>
                    <div className="nx-bar-track">
                      <div
                        className="nx-bar-fill alt"
                        style={{
                          width: `${Math.max(
                            4,
                            Math.round((alt.distanceM / maxDist) * 100)
                          )}%`,
                        }}
                      />
                    </div>
                  </div>
                )}

                {(base.exposedDistanceM > 0 ||
                  (alt?.exposedDistanceM ?? 0) > 0) && (
                  <>
                    <div className="nx-bar-group" style={{ marginTop: 10 }}>
                      <div className="nx-bar-row-label">
                        <span>Baseline Simulated Exposure</span>
                        <span className="mono">
                          {Math.round(base.exposedDistanceM)} m
                        </span>
                      </div>
                      <div className="nx-bar-track">
                        <div
                          className="nx-bar-fill hazard"
                          style={{
                            width: `${Math.max(
                              4,
                              Math.round((base.exposedDistanceM / maxExp) * 100)
                            )}%`,
                          }}
                        />
                      </div>
                    </div>
                    {alt?.feasible && (
                      <div className="nx-bar-group">
                        <div className="nx-bar-row-label">
                          <span>Hazard-Aware Simulated Exposure</span>
                          <span className="mono">
                            {Math.round(alt.exposedDistanceM)} m
                          </span>
                        </div>
                        <div className="nx-bar-track">
                          <div
                            className="nx-bar-fill alt"
                            style={{
                              width:
                                alt.exposedDistanceM > 0
                                  ? `${Math.max(
                                      4,
                                      Math.round(
                                        (alt.exposedDistanceM / maxExp) * 100
                                      )
                                    )}%`
                                  : "0%",
                            }}
                          />
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}

            {/* Corridors Used */}
            {(base?.roadSequence.length || alt?.roadSequence.length) ? (
              <div className="nx-subcard">
                <div className="nx-label-sm">Primary Road Corridors</div>
                {base && base.roadSequence.length > 0 && (
                  <div className="nx-corridor-block">
                    <span className="nx-corridor-tag base">Baseline:</span>{" "}
                    <span>{base.roadSequence.slice(0, 6).join(" → ")}</span>
                  </div>
                )}
                {alt?.feasible && alt.roadSequence.length > 0 && (
                  <div className="nx-corridor-block">
                    <span className="nx-corridor-tag alt">Alternative:</span>{" "}
                    <span>{alt.roadSequence.slice(0, 6).join(" → ")}</span>
                  </div>
                )}
              </div>
            ) : null}

            {/* Warnings */}
            {comp && comp.warnings.length > 0 && (
              <div className="nx-warn-box">
                <strong>Analysis Notes:</strong>
                <ul className="nx-bullet-list">
                  {comp.warnings.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Assumptions & Data-Quality Limitations */}
            <details className="nx-details" open>
              <summary>Assumptions, Provenance &amp; Limitations</summary>
              <div className="nx-limitations-box">
                <div className="nx-micro-head">Execution Provenance</div>
                <div className="nx-micro-note mono">
                  Source: {prov?.networkSourceLabel}
                  <br />
                  Algorithm: {prov?.algorithm}
                  <br />
                  Snap Dist: Origin {base?.snapOriginM ?? 0} m · Dest{" "}
                  {base?.snapDestinationM ?? 0} m
                </div>

                {comp && comp.assumptions.length > 0 && (
                  <>
                    <div className="nx-micro-head" style={{ marginTop: 8 }}>
                      Cost &amp; Routing Assumptions
                    </div>
                    <ul className="nx-bullet-list">
                      {comp.assumptions.map((a) => (
                        <li key={a}>{a}</li>
                      ))}
                    </ul>
                  </>
                )}

                {comp && comp.limitations.length > 0 && (
                  <>
                    <div className="nx-micro-head" style={{ marginTop: 8 }}>
                      Scenario &amp; Data Limitations
                    </div>
                    <ul className="nx-bullet-list">
                      {comp.limitations.map((l) => (
                        <li key={l}>{l}</li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            </details>

            {/* Camera & Reset Actions */}
            <div className="nx-results-footer">
              <button
                type="button"
                className="nx-btn nx-btn-secondary nx-btn-xs"
                onClick={() => mapBridge.fitToAnalysis()}
              >
                Fit Camera to Routes
              </button>
              <button
                type="button"
                className="nx-btn nx-btn-ghost nx-btn-xs"
                onClick={() => void resetDemo()}
              >
                Reset Demo
              </button>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
