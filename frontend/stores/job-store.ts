"use client";
import { create } from "zustand";
import { uid } from "@/lib/format";
import type { Job, JobStage } from "@/types";

type Store = {
  jobs: Job[];
  startJob: (title: string, kind: string, stages: JobStage[], onDone: () => void) => string;
  clearDone: () => void;
};

export const useJobStore = create<Store>((set, get) => ({
  jobs: [],
  startJob: (title, kind, stages, onDone) => {
    const id = uid("job");
    const job: Job = {
      id, title, kind, progress: 0, state: "running",
      stages: stages.map((s) => ({ ...s, state: "pending" })),
      startedAt: Date.now()
    };
    set((s) => ({ jobs: [job, ...s.jobs].slice(0, 12) }));

    let step = 0;
    const tick = () => {
      const cur = get().jobs.find((j) => j.id === id);
      if (!cur) return;
      const stagesN = cur.stages.length;
      const next = cur.stages.map((s, i) => ({ ...s, state: (i < step ? "done" : i === step ? "running" : "pending") as JobStage["state"] }));
      const progress = Math.round(((step + 0.5) / stagesN) * 100);
      set((s) => ({ jobs: s.jobs.map((j) => (j.id === id ? { ...j, stages: next, progress } : j)) }));
      step += 1;
      if (step <= stagesN) {
        setTimeout(tick, 420 + Math.random() * 380);
      } else {
        set((s) => ({
          jobs: s.jobs.map((j) => (j.id === id ? { ...j, state: "succeeded", progress: 100, stages: j.stages.map((x) => ({ ...x, state: "done" as const })) } : j))
        }));
        onDone();
      }
    };
    setTimeout(tick, 200);
    return id;
  },
  clearDone: () => set((s) => ({ jobs: s.jobs.filter((j) => j.state === "running" || j.state === "queued") }))
}));
