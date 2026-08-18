"use client";
import { create } from "zustand";
import { api } from "@/lib/api/client";
import type { Job, JobStage } from "@/types";

type Store = {
  jobs: Job[];
  startJob: (title: string, kind: string, stages: JobStage[], taskFn: () => Promise<void>) => Promise<string>;
  clearDone: () => void;
};

export const useJobStore = create<Store>((set, get) => ({
  jobs: [],
  startJob: async (title, kind, stages, taskFn) => {
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

    const jobId = backendJob.id;
    let finished = false;

    const pollInterval = setInterval(async () => {
      if (finished) return;
      try {
        const latest = await api.getJob(jobId);
        if (latest) {
          set((s) => ({
            jobs: s.jobs.map((j) => (j.id === jobId ? { ...j, ...latest } : j))
          }));
          if (latest.state === "succeeded" || latest.state === "failed") {
            finished = true;
            clearInterval(pollInterval);
          }
        }
      } catch (err: any) {
        // HTTP 404 or backend failure
        console.warn(`Job ${jobId} status poll notice:`, err?.message);
      }
    }, 800);

    // Execute real work asynchronously
    (async () => {
      try {
        await taskFn();
        finished = true;
        clearInterval(pollInterval);
        set((s) => ({
          jobs: s.jobs.map((j) => (j.id === jobId ? {
            ...j,
            state: "succeeded",
            progress: 100,
            stages: j.stages.map((x) => ({ ...x, state: "done" as const }))
          } : j))
        }));
      } catch (err: any) {
        finished = true;
        clearInterval(pollInterval);
        set((s) => ({
          jobs: s.jobs.map((j) => (j.id === jobId ? {
            ...j,
            state: "failed",
            error: err.message || "Job execution failed"
          } : j))
        }));
      }
    })();

    return jobId;
  },
  clearDone: () => set((s) => ({ jobs: s.jobs.filter((j) => j.state === "running" || j.state === "queued") }))
}));
