"use client";
import { create } from "zustand";

export type DrawMode = "select" | "road" | "hospital" | "school" | "fire" | "zone" | "measure";

type Store = {
  ready: boolean;
  error: string | null;
  demo: boolean;
  year: number;
  playing: boolean;
  drawMode: DrawMode;
  drawnPath: [number, number][];
  cameraText: string;
  /** Last map click in lon/lat with monotonic seq so panels only react to new clicks. */
  lastClick: { lon: number; lat: number; seq: number } | null;
  clickSeq: number;
  incidentPickActive: boolean;
  setReady: (v: boolean) => void;
  setError: (e: string | null) => void;
  setDemo: (v: boolean) => void;
  setYear: (y: number) => void;
  setPlaying: (v: boolean) => void;
  setDrawMode: (m: DrawMode) => void;
  setDrawnPath: (p: [number, number][]) => void;
  setCameraText: (t: string) => void;
  setLastClick: (c: { lon: number; lat: number } | null) => void;
  setIncidentPickActive: (v: boolean) => void;
};

export const useMapStore = create<Store>((set) => ({
  ready: false,
  error: null,
  // Starts true only until the first /ready probe resolves. Wired to real
  // backend reachability by BackendStatusBanner - never hardcode this, or the
  // badge reports DEMO DATA while showing genuine database results.
  demo: true,
  year: 2026,
  playing: false,
  drawMode: "select",
  drawnPath: [],
  cameraText: "",
  lastClick: null,
  clickSeq: 0,
  incidentPickActive: false,
  setReady: (v) => set({ ready: v }),
  setError: (e) => set({ error: e }),
  setDemo: (v) => set({ demo: v }),
  setYear: (y) => set({ year: y }),
  setPlaying: (v) => set({ playing: v }),
  setDrawMode: (m) => set({ drawMode: m, drawnPath: m === "road" ? [] : [] }),
  setDrawnPath: (p) => set({ drawnPath: p }),
  setCameraText: (t) => set({ cameraText: t }),
  setLastClick: (c) =>
    set((s) => {
      if (!c) return { lastClick: null };
      const nextSeq = s.clickSeq + 1;
      return {
        clickSeq: nextSeq,
        lastClick: { lon: c.lon, lat: c.lat, seq: nextSeq },
      };
    }),
  setIncidentPickActive: (v) => set({ incidentPickActive: v }),
}));
