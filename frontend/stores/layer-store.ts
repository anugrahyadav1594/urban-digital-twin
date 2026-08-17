"use client";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Layer, LayerKind } from "@/types";
import { FACILITIES, PARCELS, ROADS, ZONE_COLOR, ZONE_LABEL } from "@/lib/city-model";
import { api } from "@/lib/api/client";

const initial: Layer[] = [
  { id: "buildings", name: "Buildings (3D)", group: "Base", visible: true, opacity: 1, color: "#8ea6c8", count: PARCELS.filter((p) => p.floors > 0).length },
  { id: "parcels", name: "Parcels", group: "Semantic", visible: false, opacity: 0.75, color: "#22d3ee", count: PARCELS.length },
  { id: "roads", name: "Road network", group: "Base", visible: true, opacity: 0.9, color: "#f8fafc", count: ROADS.length },
  { id: "highways", name: "National Highways", group: "Base", visible: true, opacity: 1.0, color: "#38bdf8", count: 8 },
  { id: "landuse", name: "Land use", group: "Semantic", visible: false, opacity: 0.6, color: "#facc15", count: PARCELS.length,
    legend: Object.keys(ZONE_LABEL).map((z) => ({ label: z + " — " + ZONE_LABEL[z], color: ZONE_COLOR[z] })) },
  { id: "population", name: "Population density", group: "Semantic", visible: false, opacity: 0.7, color: "#fb7185", count: PARCELS.length,
    legend: [{ label: "0 - 200", color: "#1e3a8a" }, { label: "200 - 500", color: "#7c3aed" }, { label: "500 - 800", color: "#e11d48" }, { label: "800+", color: "#fb923c" }] },
  { id: "water", name: "Water bodies", group: "Base", visible: true, opacity: 0.8, color: "#38bdf8", count: 1 },
  { id: "flood", name: "Flood risk (100y)", group: "Risk", visible: false, opacity: 0.55, color: "#ef4444", count: PARCELS.filter((p) => p.flood !== "Low").length,
    legend: [{ label: "Low", color: "#22c55e" }, { label: "Medium", color: "#f59e0b" }, { label: "High", color: "#ef4444" }] },
  { id: "facilities", name: "Public facilities", group: "Semantic", visible: true, opacity: 1, color: "#34d399", count: FACILITIES.length },
  { id: "candidates", name: "Analysis candidates", group: "Planning", visible: true, opacity: 1, color: "#fde047", count: 0 },
  { id: "proposals", name: "Scenario proposals", group: "Planning", visible: true, opacity: 1, color: "#a855f7", count: 0 }
];

type Store = {
  layers: Layer[];
  setVisible: (id: LayerKind, v: boolean) => void;
  setOpacity: (id: LayerKind, o: number) => void;
  setCount: (id: LayerKind, c: number) => void;
  syncFromBackend: () => Promise<void>;
  soloGroup: (group: Layer["group"]) => void;
  reset: () => void;
};

export const useLayerStore = create<Store>()(
  persist(
    (set) => ({
      layers: initial,
      setVisible: (id, v) =>
        set((s) => {
          const exists = s.layers.some((l) => l.id === id);
          if (!exists) {
            const initLayer = initial.find((l) => l.id === id) ?? {
              id, name: "Highways & Expressways", group: "Base", visible: v, opacity: 1.0, color: "#38bdf8", count: ROADS.filter((r) => r.type === "Arterial").length
            };
            return { layers: [...s.layers, { ...initLayer, visible: v }] };
          }
          return { layers: s.layers.map((l) => (l.id === id ? { ...l, visible: v } : l)) };
        }),
      setOpacity: (id, o) => set((s) => ({ layers: s.layers.map((l) => (l.id === id ? { ...l, opacity: o } : l)) })),
      setCount: (id, c) => set((s) => ({ layers: s.layers.map((l) => (l.id === id ? { ...l, count: c } : l)) })),
      /**
       * Replace synthetic counts with real PostGIS row counts.
       * Only counts are taken from the server; visibility/opacity/colour stay
       * client-side so the user's toggles survive a refresh.
       */
      syncFromBackend: async () => {
        const live = await api.listLayers();
        if (!live) return;
        const byId = new Map(live.map((l) => [String(l.id), l]));
        set((s) => ({
          layers: s.layers.map((l) => {
            const m = byId.get(String(l.id));
            return m && typeof m.count === "number" ? { ...l, count: m.count } : l;
          })
        }));
      },
      soloGroup: (group) => set((s) => ({ layers: s.layers.map((l) => ({ ...l, visible: l.group === group })) })),
      reset: () => set({ layers: initial })
    }),
    {
      name: "nagarx.layers.v2",
      merge: (persistedState: any, currentState) => {
        const persistedLayers: Layer[] = persistedState?.layers ?? [];
        const mergedLayers = initial.map((initLayer) => {
          const found = persistedLayers.find((l) => l.id === initLayer.id);
          return found ? { ...initLayer, visible: found.visible, opacity: found.opacity } : initLayer;
        });
        return { ...currentState, layers: mergedLayers };
      }
    }
  )
);
