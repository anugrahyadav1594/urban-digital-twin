"use client";
import { create } from "zustand";
import { api } from "@/lib/api/client";
import { uid } from "@/lib/format";
import type { Scenario, ScenarioChange } from "@/types";

type Store = {
  scenarios: Scenario[];
  activeId: string;
  loading: boolean;
  error: string | null;
  active: () => Scenario;
  setActive: (id: string) => void;
  loadScenarios: () => Promise<void>;
  createScenario: (name: string, horizon: number, growth: number, description?: string) => Promise<void>;
  addChange: (change: Omit<ScenarioChange, "id"> & { parameters?: any; object_id?: number }) => Promise<void>;
  setStatus: (id: string, status: Scenario["status"]) => Promise<void>;
  setGrowth: (id: string, pct: number) => Promise<void>;
};

export const useScenarioStore = create<Store>((set, get) => ({
  scenarios: [],
  activeId: "",
  loading: false,
  error: null,
  active: () => get().scenarios.find((s) => s.id === get().activeId) ?? get().scenarios[0] ?? {
    id: "1", name: "Base City", status: "baseline", createdAt: new Date().toISOString(), horizon: 2035, populationGrowthPct: 2.5, changes: []
  },
  setActive: (id) => set({ activeId: id }),
  loadScenarios: async () => {
    set({ loading: true, error: null });
    try {
      const data = await api.listScenarios();
      set({ scenarios: data, activeId: get().activeId || (data[0]?.id ?? ""), loading: false });
    } catch (err: any) {
      console.error("Failed to load scenarios:", err);
      set({ error: err.message || "Failed to load scenarios", loading: false });
    }
  },
  createScenario: async (name, horizon, growth, description) => {
    set({ loading: true, error: null });
    try {
      const created = await api.createScenario(name, horizon, growth, description);
      set((s) => ({
        scenarios: [...s.scenarios, created],
        activeId: created.id,
        loading: false
      }));
    } catch (err: any) {
      console.error("Failed to create scenario:", err);
      set({ error: err.message || "Scenario creation failed", loading: false });
      alert(`Scenario creation failed: ${err.message || "Backend error"}`);
    }
  },
  addChange: async (change) => {
    const activeId = get().activeId;
    if (!activeId) return;
    try {
      await api.addScenarioChange(activeId, {
        type: change.type,
        label: change.label,
        parameters: change.parameters || { detail: change.detail },
        object_id: change.object_id
      });
      // Refresh list to keep Zustand and postgis canonical
      const updatedList = await api.listScenarios();
      set({ scenarios: updatedList });
    } catch (err: any) {
      console.error("Failed to persist change:", err);
      alert(`Failed to persist scenario change: ${err.message || "Backend error"}`);
    }
  },
  setStatus: async (id, status) => {
    try {
      const updated = await api.updateScenario(id, { status });
      set((s) => ({
        scenarios: s.scenarios.map((x) => (x.id === id ? { ...x, status: updated.status } : x))
      }));
    } catch (err: any) {
      console.error("Failed to update status:", err);
      alert(`Status update failed: ${err.message || "Backend error"}`);
    }
  },
  setGrowth: async (id, pct) => {
    try {
      const updated = await api.updateScenario(id, { populationGrowthPct: pct });
      set((s) => ({
        scenarios: s.scenarios.map((x) => (x.id === id ? { ...x, populationGrowthPct: updated.populationGrowthPct } : x))
      }));
    } catch (err: any) {
      console.error("Failed to update growth:", err);
      alert(`Growth update failed: ${err.message || "Backend error"}`);
    }
  }
}));