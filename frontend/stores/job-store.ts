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
    let isLocalOnly = false;
    try {
      backendJob = await api.createJob(title, kind, stages);
    } catch {
      isLocalOnly = true;
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

    // Poll backend for authoritative job state (only for backend-managed jobs)
    const pollInterval = !isLocalOnly ? setInterval(async () => {
      if (finished) return;
      try {
        const latest = await api.getJob(jobId);
        if (latest) {
          set((s) => ({
            jobs: s.jobs.map((j) => (j.id === jobId ? { ...j, ...latest } : j))
          }));
          if (latest.state === "succeeded" || latest.state === "failed") {
            finished = true;
            clearInterval(pollInterval!);
          }
        }
      } catch (err: any) {
        console.warn(`Job ${jobId} status poll notice:`, err?.message);
      }
    }, 800) : null;

    // Execute real work asynchronously
    (async () => {
      try {
        await taskFn();
        // Signal the backend that the task completed
        if (!isLocalOnly && !finished) {
          await api.updateJob(jobId, {
            state: "succeeded",
            progress: 100,
            stages: stages.map((s) => ({ ...s, state: "done" as const }))
          });
          // Polling will pick up the terminal state; give it one cycle
        } else {
          // Local-only fallback: no backend to poll
          finished = true;
          set((s) => ({
            jobs: s.jobs.map((j) => (j.id === jobId ? {
              ...j,
              state: "succeeded",
              progress: 100,
              stages: j.stages.map((x) => ({ ...x, state: "done" as const }))
            } : j))
          }));
        }
      } catch (err: any) {
        // Signal the backend that the task failed
        if (!isLocalOnly && !finished) {
          await api.updateJob(jobId, {
            state: "failed",
            error: err.message || "Job execution failed"
          }).catch(() => {});
        }
        // Always update local state for failures (user needs immediate feedback)
        finished = true;
        if (pollInterval) clearInterval(pollInterval);
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

