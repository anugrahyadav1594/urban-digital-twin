"use client";
import { create } from "zustand";
import type { AgentStep, ChatMessage } from "@/types";
import { uid } from "@/lib/format";

type Store = {
  messages: ChatMessage[];
  steps: AgentStep[];
  thinking: boolean;
  push: (m: Omit<ChatMessage, "id">) => string;
  updateLast: (patch: Partial<ChatMessage>) => void;
  setSteps: (s: AgentStep[]) => void;
  pushStep: (s: Omit<AgentStep, "id">) => void;
  completeSteps: () => void;
  setThinking: (v: boolean) => void;
  reset: () => void;
};

export const useAIStore = create<Store>((set) => ({
  messages: [
    { id: "m0", role: "assistant", text: "Planning Assistant ready. I orchestrate the deterministic GIS, network, risk and optimisation engines - every number I quote comes from a tool run, not from the language model.\n\nTry: \"Where should we build a new hospital?\"" }
  ],
  steps: [],
  thinking: false,
  push: (m) => {
    const id = uid("msg");
    set((s) => ({ messages: [...s.messages, { ...m, id }] }));
    return id;
  },
  updateLast: (patch) =>
    set((s) => {
      const messages = [...s.messages];
      messages[messages.length - 1] = { ...messages[messages.length - 1], ...patch };
      return { messages };
    }),
  setSteps: (steps) => set({ steps }),
  pushStep: (s0) => set((s) => ({ steps: [...s.steps.map((x) => ({ ...x, state: "done" as const })), { ...s0, id: uid("step") }] })),
  completeSteps: () => set((s) => ({ steps: s.steps.map((x) => ({ ...x, state: "done" as const })) })),
  setThinking: (v) => set({ thinking: v }),
  reset: () => set({ messages: [], steps: [] })
}));
