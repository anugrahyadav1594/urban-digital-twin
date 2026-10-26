"use client";

import React from "react";
import { useLayerStore } from "@/stores/layer-store";
import { useMapStore } from "@/stores/map-store";
import { useRouteAnalysisStore } from "@/stores/route-analysis-store";
import type { LayerKind } from "@/types";

const QUICK_LAYERS: { id: LayerKind; label: string }[] = [
  { id: "roads", label: "Roads" },
  { id: "buildings", label: "Buildings" },
  { id: "water", label: "Water" },
  { id: "facilities", label: "Landmarks" },
  { id: "highways", label: "Highways" },
];

export default function MapOverlayControls() {
  const leftPanelOpen = useRouteAnalysisStore((s) => s.leftPanelOpen);
  const legendOpen = useRouteAnalysisStore((s) => s.legendOpen);
  const setLegendOpen = useRouteAnalysisStore((s) => s.setLegendOpen);

  const layers = useLayerStore((s) => s.layers);
  const setLayerVisible = useLayerStore((s) => s.setVisible);
  const cameraText = useMapStore((s) => s.cameraText);

  return (
    <div
      className="nx-map-overlay-dock"
      style={{
        left: leftPanelOpen ? 404 : 16,
      }}
      aria-label="Map Legend and Quick Layer Controls"
    >
      {/* Quick Layer Strip */}
      <div className="nx-quick-layers" role="group" aria-label="Map Layers">
        {QUICK_LAYERS.map((ql) => {
          const visible =
            layers.find((l) => l.id === ql.id)?.visible ?? false;
          return (
            <button
              key={ql.id}
              type="button"
              className={"nx-layer-chip" + (visible ? " on" : "")}
              onClick={() => setLayerVisible(ql.id, !visible)}
              aria-pressed={visible}
              title={`Toggle ${ql.label} layer`}
            >
              {ql.label}
            </button>
          );
        })}
        <button
          type="button"
          className={"nx-layer-chip legend-btn" + (legendOpen ? " on" : "")}
          onClick={() => setLegendOpen(!legendOpen)}
          aria-expanded={legendOpen}
        >
          {legendOpen ? "Hide Legend" : "Legend"}
        </button>
      </div>

      {/* Map Legend */}
      {legendOpen && (
        <div className="nx-legend-card" role="note" aria-label="Map Symbol Legend">
          <div className="nx-legend-title">MAP SYMBOL LEGEND</div>
          <div className="nx-legend-grid">
            <div className="nx-legend-item">
              <span className="nx-sym-pin orig" aria-hidden="true">
                A
              </span>
              <span>Origin (A)</span>
            </div>
            <div className="nx-legend-item">
              <span className="nx-sym-pin dest" aria-hidden="true">
                B
              </span>
              <span>Destination (B)</span>
            </div>
            <div className="nx-legend-item">
              <span className="nx-sym-line baseline" aria-hidden="true" />
              <span>Baseline Route (Dashed Blue)</span>
            </div>
            <div className="nx-legend-item">
              <span className="nx-sym-line alt" aria-hidden="true" />
              <span>Hazard-Aware Alt (Solid Orange)</span>
            </div>
            <div className="nx-legend-item">
              <span className="nx-sym-line closed" aria-hidden="true" />
              <span>Impassable Segment (Red)</span>
            </div>
            <div className="nx-legend-item">
              <span className="nx-sym-line penalized" aria-hidden="true" />
              <span>Penalized Segment (Dashed Amber)</span>
            </div>
            <div className="nx-legend-item">
              <span className="nx-sym-zone" aria-hidden="true" />
              <span>Simulated Hazard Footprint</span>
            </div>
          </div>
          <div className="nx-telemetry mono">{cameraText}</div>
        </div>
      )}
    </div>
  );
}
