"use client";
import { create } from "zustand";
import { SCENARIOS } from "@/lib/mock";
import { uid } from "@/lib/format";
import type { Scenario, ScenarioChange } from "@/types";

type Store = {
  scenarios: Scenario[];
  activeId: string;
  active: () => Scenario;
  setActive: (id: string) => void;
  createScenario: (name: string, horizon: number, growth: number) => void;
  addChange: (change: Omit<ScenarioChange, "id">) => void;
  setStatus: (id: string, status: Scenario["status"]) => void;
  setGrowth: (id: string, pct: number) => void;
};

export const useScenarioStore = create<Store>((set, get) => ({
  scenarios: SCENARIOS,
  activeId: "scn_plan_a",
  active: () => get().scenarios.find((s) => s.id === get().activeId) ?? get().scenarios[0],
  setActive: (id) => set({ activeId: id }),
  createScenario: (name, horizon, growth) =>
    set((s) => {
      const scn: Scenario = { id: uid("scn"), name, status: "draft", createdAt: new Date().toISOString().slice(0, 10), horizon, populationGrowthPct: growth, changes: [] };
      return { scenarios: [...s.scenarios, scn], activeId: scn.id };
    }),
  addChange: (change) =>
    set((s) => ({
      scenarios: s.scenarios.map((x) => (x.id === s.activeId ? { ...x, changes: [...x.changes, { ...change, id: uid("chg") }] } : x))
    })),
  setStatus: (id, status) => set((s) => ({ scenarios: s.scenarios.map((x) => (x.id === id ? { ...x, status } : x)) })),
  setGrowth: (id, pct) => set((s) => ({ scenarios: s.scenarios.map((x) => (x.id === id ? { ...x, populationGrowthPct: pct } : x)) }))
}));
