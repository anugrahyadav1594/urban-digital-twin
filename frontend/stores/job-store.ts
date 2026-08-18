"use client";
import { create } from "zustand";
import { api } from "@/lib/api/client";
import type { Job, JobStage } from "@/types";

type Store = {
  jobs: Job[];
  startJob: (title: string, kind: string, stages: JobStage[], onDone: () => Promise<void> | void) => Promise<string>;
  clearDone: () => void;
};

export const useJobStore = create<Store>((set, get) => ({
  jobs: [],
  startJob: async (title, kind, stages, onDone) => {
    let backendJob: Job;
    try {
      backendJob = await api.createJob(title, kind, stages);
    } catch {
      backendJob = {
        id: `job_${Date.now()}`,
        title,
        kind,
        progress: 10,
        state: "running",
        stages: stages.map((s, i) => ({ ...s, state: i === 0 ? "running" : "pending" })),
        startedAt: Date.now()
      };
    }

    set((s) => ({ jobs: [backendJob, ...s.jobs].slice(0, 12) }));

    const pollInterval = setInterval(async () => {
      try {
        const latest = await api.getJob(backendJob.id);
        if (latest) {
          set((s) => ({
            jobs: s.jobs.map((j) => (j.id === backendJob.id ? { ...j, ...latest } : j))
          }));
          if (latest.state === "succeeded" || latest.state === "failed") {
            clearInterval(pollInterval);
            await onDone();
          }
          return;
        }
      } catch (err) {
        console.warn("Job status poll error:", err);
      }
    }, 800);

    // Run task logic asynchronously
    (async () => {
      try {
        await onDone();
        clearInterval(pollInterval);
        set((s) => ({
          jobs: s.jobs.map((j) => (j.id === backendJob.id ? {
            ...j,
            state: "succeeded",
            progress: 100,
            stages: j.stages.map((x) => ({ ...x, state: "done" as const }))
          } : j))
        }));
      } catch (err: any) {
        clearInterval(pollInterval);
        set((s) => ({
          jobs: s.jobs.map((j) => (j.id === backendJob.id ? {
            ...j,
            state: "failed",
            error: err.message || "Job execution failed"
          } : j))
        }));
      }
    })();

    return backendJob.id;
  },
  clearDone: () => set((s) => ({ jobs: s.jobs.filter((j) => j.state === "running" || j.state === "queued") }))
}));
