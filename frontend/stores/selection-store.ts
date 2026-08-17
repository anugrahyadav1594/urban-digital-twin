"use client";
import { create } from "zustand";
import type { FeatureRecord } from "@/types";
import { api } from "@/lib/api/client";

type Store = {
  selectedId: string | null;
  feature: FeatureRecord | null;
  loading: boolean;
  history: string[];
  select: (id: string | null) => Promise<void>;
};

export const useSelectionStore = create<Store>((set, get) => ({
  selectedId: null,
  feature: null,
  loading: false,
  history: [],
  select: async (id) => {
    if (!id) return set({ selectedId: null, feature: null });
    set({ selectedId: id, loading: true });
    const feature = await api.getFeature(id);
    const history = [id, ...get().history.filter((h) => h !== id)].slice(0, 8);
    set({ feature, loading: false, history });
  }
}));
