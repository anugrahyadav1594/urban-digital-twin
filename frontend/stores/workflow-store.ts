"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { WORKFLOWS, type WorkflowDef, type WorkflowId, type WorkflowStepDef, getWorkflow } from "@/lib/workflows";
import { useWindowStore } from "./window-store";
import { useLayerStore } from "./layer-store";
import type { LayerKind } from "@/types";

export type WorkflowContext = {
  backendSessionId?: string;
  activeCandidateId?: string;
  activeResultId?: string;
  activeScenarioId?: string;
  hazardType?: string;
  incidentPos?: { lon: number; lat: number };
  simData?: any;
  customData?: Record<string, any>;
};

type WorkflowStore = {
  activeWorkflowId: WorkflowId | null;
  currentStepIndex: number;
  completedStepIds: string[];
  context: WorkflowContext;

  currentWorkflow: () => WorkflowDef | null;
  currentStep: () => WorkflowStepDef | null;

  startWorkflow: (id: WorkflowId, initialStepIndex?: number) => Promise<void>;
  advanceStep: () => void;
  prevStep: () => void;
  jumpToStep: (stepIdOrIndex: string | number) => void;
  completeStep: (stepId: string) => void;
  setContext: (patch: Partial<WorkflowContext>) => void;
  cancelWorkflow: () => void;
};

function activateWorkflowEnvironment(workflowId: WorkflowId, stepIndex: number) {
  const def = getWorkflow(workflowId);
  if (!def) return;
  const step = def.steps[stepIndex] ?? def.steps[0];
  if (!step) return;

  const windowStore = useWindowStore.getState();
  const layerStore = useLayerStore.getState();

  // 1. Open target window
  if (step.targetWindow) {
    windowStore.openWindow(step.targetWindow);
  }

  // 2. Open auxiliary window if specified
  if (step.auxWindows?.length) {
    step.auxWindows.forEach((w) => {
      windowStore.openWindow(w);
    });
  }

  // 3. Highlight relevant layers for this step
  if (step.relevantLayers?.length) {
    step.relevantLayers.forEach((layerId: LayerKind) => {
      layerStore.setVisible(layerId, true);
    });
  }
}

export const useWorkflowStore = create<WorkflowStore>()(
  persist(
    (set, get) => ({
      activeWorkflowId: null,
      currentStepIndex: 0,
      completedStepIds: [],
      context: {},

      currentWorkflow: () => {
        const id = get().activeWorkflowId;
        return id ? getWorkflow(id) : null;
      },

      currentStep: () => {
        const wf = get().currentWorkflow();
        if (!wf) return null;
        return wf.steps[get().currentStepIndex] ?? null;
      },

      startWorkflow: async (id: WorkflowId, initialStepIndex = 0) => {
        const def = getWorkflow(id);
        const validIndex = Math.min(Math.max(0, initialStepIndex), def.steps.length - 1);
        set({
          activeWorkflowId: id,
          currentStepIndex: validIndex,
          completedStepIds: []
        });
        activateWorkflowEnvironment(id, validIndex);

        // Initiate backend workflow session
        try {
          const { api } = await import("@/lib/api/client");
          const sessionEnv = await api.startWorkflow(id);
          if (sessionEnv?.session_id) {
            set((s) => ({
              context: { ...s.context, backendSessionId: sessionEnv.session_id }
            }));
          }
        } catch (e) {
          console.warn("Backend workflow session init warning:", e);
        }
      },

      advanceStep: () => {
        const { activeWorkflowId, currentStepIndex, completedStepIds } = get();
        if (!activeWorkflowId) return;
        const def = getWorkflow(activeWorkflowId);
        const currentStep = def.steps[currentStepIndex];

        const nextCompleted = currentStep && !completedStepIds.includes(currentStep.id)
          ? [...completedStepIds, currentStep.id]
          : completedStepIds;

        if (currentStepIndex < def.steps.length - 1) {
          const nextIndex = currentStepIndex + 1;
          set({
            currentStepIndex: nextIndex,
            completedStepIds: nextCompleted
          });
          activateWorkflowEnvironment(activeWorkflowId, nextIndex);
        } else {
          set({ completedStepIds: nextCompleted });
        }
      },

      prevStep: () => {
        const { activeWorkflowId, currentStepIndex } = get();
        if (!activeWorkflowId || currentStepIndex <= 0) return;
        const prevIndex = currentStepIndex - 1;
        set({ currentStepIndex: prevIndex });
        activateWorkflowEnvironment(activeWorkflowId, prevIndex);
      },

      jumpToStep: (stepIdOrIndex) => {
        const { activeWorkflowId } = get();
        if (!activeWorkflowId) return;
        const def = getWorkflow(activeWorkflowId);

        let targetIndex = 0;
        if (typeof stepIdOrIndex === "number") {
          targetIndex = Math.min(Math.max(0, stepIdOrIndex), def.steps.length - 1);
        } else {
          const found = def.steps.findIndex((s) => s.id === stepIdOrIndex);
          if (found >= 0) targetIndex = found;
        }

        set({ currentStepIndex: targetIndex });
        activateWorkflowEnvironment(activeWorkflowId, targetIndex);
      },

      completeStep: (stepId) => {
        set((s) => ({
          completedStepIds: s.completedStepIds.includes(stepId)
            ? s.completedStepIds
            : [...s.completedStepIds, stepId]
        }));
      },

      setContext: (patch) => {
        set((s) => ({
          context: { ...s.context, ...patch }
        }));
      },

      cancelWorkflow: () => {
        set({
          activeWorkflowId: null,
          currentStepIndex: 0,
          completedStepIds: [],
          context: {}
        });
      }
    }),
    {
      name: "nagarx.active.workflow.v1",
      partialize: (s) => ({
        activeWorkflowId: s.activeWorkflowId,
        currentStepIndex: s.currentStepIndex,
        completedStepIds: s.completedStepIds,
        context: s.context
      })
    }
  )
);
