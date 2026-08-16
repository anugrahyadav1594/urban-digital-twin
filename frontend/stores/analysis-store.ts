"use client";
import { create } from "zustand";
import type { AnalysisResult } from "@/types";

type Store = {
  results: AnalysisResult[];
  activeId: string | null;
  active: () => AnalysisResult | null;
  addResult: (r: AnalysisResult) => void;
  setActive: (id: string) => void;
  clear: () => void;
};

export const useAnalysisStore = create<Store>((set, get) => ({
  results: [],
  activeId: null,
  active: () => get().results.find((r) => r.resultId === get().activeId) ?? null,
  addResult: (r) => set((s) => ({ results: [r, ...s.results].slice(0, 10), activeId: r.resultId })),
  setActive: (id) => set({ activeId: id }),
  clear: () => set({ results: [], activeId: null })
}));
