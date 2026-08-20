"use client";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import { NAVBAR_HEIGHT, TASKBAR_HEIGHT } from "@/lib/constants";

export type WindowId =
  | "city" | "layers" | "legend" | "inspector" | "scenario" | "changes"
  | "planning" | "analysis" | "results" | "simulation" | "jobs"
  | "emergency" | "regions" | "scorecard" | "development"
  | "comparison" | "ai" | "trace";

export type Pin = "none" | "left" | "right";

export type WindowState = {
  id: WindowId;
  title: string;
  x: number; y: number;
  width: number; height: number;
  minWidth: number; minHeight: number;
  zIndex: number;
  minimized: boolean;
  maximized: boolean;
  visible: boolean;
  pin: Pin;
  restore?: { x: number; y: number; width: number; height: number };
};

export type WindowDef = {
  title: string;
  icon: string;
  defaultSize: { width: number; height: number };
  minSize: { width: number; height: number };
  defaultPos?: { x: number; y: number };
};

/** Central registry - add a tool here and it is instantly available
 *  to the navbar, command palette, presets and window manager. */
export const WINDOW_REGISTRY: Record<WindowId, WindowDef> = {
  city:       { title: "City Information",   icon: "◈", defaultSize: { width: 340, height: 420 }, minSize: { width: 280, height: 260 }, defaultPos: { x: 24, y: 70 } },
  layers:     { title: "Layers",             icon: "≣", defaultSize: { width: 320, height: 500 }, minSize: { width: 260, height: 300 }, defaultPos: { x: 24, y: 70 } },
  legend:     { title: "Legend",             icon: "▦", def: { width: 280, height: 330 }, minSize: { width: 220, height: 220 }, defaultPos: { x: 24, y: 590 } },
  inspector:  { title: "Object Inspector",   icon: "◎", defaultSize: { width: 360, height: 500 }, minSize: { width: 300, height: 350 }, defaultPos: { x: -390, y: 70 } },
  scenario:   { title: "Scenario Manager",   icon: "⌘", defaultSize: { width: 380, height: 460 }, minSize: { width: 320, height: 300 }, defaultPos: { x: 370, y: 90 } },
  changes:    { title: "Scenario Changes",   icon: "≡", defaultSize: { width: 380, height: 360 }, minSize: { width: 300, height: 240 }, defaultPos: { x: 400, y: 420 } },
  planning:   { title: "Planning Tools",     icon: "⚒", defaultSize: { width: 420, height: 640 }, minSize: { width: 400, height: 400 }, defaultPos: { x: 360, y: 70 } },
  analysis:   { title: "Analysis",           icon: "⌗", defaultSize: { width: 520, height: 440 }, minSize: { width: 400, height: 300 }, defaultPos: { x: 470, y: 330 } },
  results:    { title: "Results",            icon: "◳", defaultSize: { width: 520, height: 420 }, minSize: { width: 400, height: 300 }, defaultPos: { x: 520, y: 380 } },
  simulation: { title: "Simulation",         icon: "▶", defaultSize: { width: 520, height: 300 }, minSize: { width: 420, height: 250 }, defaultPos: { x: 300, y: 640 } },
  emergency:  { title: "Emergency Response", icon: "✚", defaultSize: { width: 430, height: 660 }, minSize: { width: 380, height: 420 }, defaultPos: { x: 800, y: 70 } },
  regions:    { title: "Regions",            icon: "◍", defaultSize: { width: 340, height: 460 }, minSize: { width: 280, height: 300 }, defaultPos: { x: 24, y: 120 } },
  scorecard:  { title: "City Scorecard",     icon: "◉", defaultSize: { width: 360, height: 620 }, minSize: { width: 300, height: 380 }, defaultPos: { x: 24, y: 70 } },
  development:{ title: "Development Planner", icon: "◈", defaultSize: { width: 400, height: 660 }, minSize: { width: 340, height: 420 }, defaultPos: { x: 400, y: 70 } },
  jobs:       { title: "Job Monitor",        icon: "◔", defaultSize: { width: 380, height: 380 }, minSize: { width: 320, height: 260 }, defaultPos: { x: -400, y: 600 } },
  comparison: { title: "Scenario Comparison",icon: "⚖", defaultSize: { width: 640, height: 440 }, minSize: { width: 500, height: 350 }, defaultPos: { x: 260, y: 200 } },
  ai:         { title: "Planning Assistant", icon: "✦", defaultSize: { width: 430, height: 620 }, minSize: { width: 350, height: 400 }, defaultPos: { x: -460, y: 90 } },
  trace:      { title: "Agent Trace",        icon: "∴", defaultSize: { width: 400, height: 420 }, minSize: { width: 320, height: 280 }, defaultPos: { x: -880, y: 300 } }
};

export const PRESETS: Record<string, WindowId[]> = {
  Default: ["layers", "inspector"],
  Planning: ["layers", "planning", "inspector"],
  Analysis: ["layers", "analysis", "results", "inspector"],
  "Scenario Comparison": ["scenario", "comparison", "changes"],
  "AI Planning": ["ai", "trace", "results", "inspector"],
  "Emergency Response": ["layers", "emergency", "inspector"]
};

type Store = {
  windows: Record<string, WindowState>;
  order: WindowId[];
  top: number;
  hydrated: boolean;
  activeId: WindowId | null;
  openWindow: (id: WindowId) => void;
  toggleWindow: (id: WindowId) => void;
  closeWindow: (id: WindowId) => void;
  focusWindow: (id: WindowId) => void;
  moveWindow: (id: WindowId, x: number, y: number) => void;
  resizeWindow: (id: WindowId, r: { x: number; y: number; width: number; height: number }) => void;
  minimizeWindow: (id: WindowId) => void;
  maximizeWindow: (id: WindowId) => void;
  pinWindow: (id: WindowId, pin: Pin) => void;
  resetWindow: (id: WindowId) => void;
  applyPreset: (name: string) => void;
  autoArrangeWindows: () => void;
  closeAll: () => void;
  setHydrated: () => void;
};

const vw = () => (typeof window === "undefined" ? 1600 : window.innerWidth);
const vh = () => (typeof window === "undefined" ? 900 : window.innerHeight);

export function computeAutoLayout(
  windows: Record<string, WindowState>,
  order: WindowId[],
  top: number
): Record<string, WindowState> {
  const openIds = order.filter(
    (id) => windows[id] && windows[id].visible && !windows[id].minimized && windows[id].pin === "none"
  );
  if (openIds.length === 0) return windows;

  const viewW = vw();
  const viewH = vh();
  const topY = NAVBAR_HEIGHT + 10;
  const usableW = Math.max(360, viewW - 32);
  const usableH = Math.max(300, viewH - NAVBAR_HEIGHT - TASKBAR_HEIGHT - 20);

  const N = openIds.length;
  const updated = { ...windows };

  if (N === 1) {
    const id = openIds[0];
    const def = WINDOW_REGISTRY[id];
    const w = Math.min(def?.defaultSize.width ?? 440, usableW);
    const h = Math.min(def?.defaultSize.height ?? 500, usableH);
    updated[id] = {
      ...updated[id],
      x: 20,
      y: topY,
      width: w,
      height: h,
      maximized: false
    };
  } else if (N === 2) {
    const gap = 12;
    const w = Math.floor((usableW - gap) / 2);
    openIds.forEach((id, idx) => {
      const def = WINDOW_REGISTRY[id];
      const h = Math.min(def?.defaultSize.height ?? 520, usableH);
      updated[id] = {
        ...updated[id],
        x: 16 + idx * (w + gap),
        y: topY,
        width: Math.max(updated[id].minWidth, w),
        height: Math.max(updated[id].minHeight, h),
        maximized: false
      };
    });
  } else if (N === 3) {
    const gap = 12;
    const leftW = Math.floor(usableW * 0.42);
    const rightW = Math.floor(usableW - leftW - gap);
    const rightH = Math.floor((usableH - gap) / 2);

    const id0 = openIds[0];
    updated[id0] = {
      ...updated[id0],
      x: 16,
      y: topY,
      width: Math.max(updated[id0].minWidth, leftW),
      height: usableH,
      maximized: false
    };

    const id1 = openIds[1];
    updated[id1] = {
      ...updated[id1],
      x: 16 + leftW + gap,
      y: topY,
      width: Math.max(updated[id1].minWidth, rightW),
      height: Math.max(updated[id1].minHeight, rightH),
      maximized: false
    };

    const id2 = openIds[2];
    updated[id2] = {
      ...updated[id2],
      x: 16 + leftW + gap,
      y: topY + rightH + gap,
      width: Math.max(updated[id2].minWidth, rightW),
      height: Math.max(updated[id2].minHeight, rightH),
      maximized: false
    };
  } else {
    const cols = Math.ceil(Math.sqrt(N));
    const rows = Math.ceil(N / cols);
    const gap = 10;
    const cellW = Math.floor((usableW - (cols - 1) * gap) / cols);
    const cellH = Math.floor((usableH - (rows - 1) * gap) / rows);

    openIds.forEach((id, idx) => {
      const c = idx % cols;
      const r = Math.floor(idx / cols);
      updated[id] = {
        ...updated[id],
        x: 16 + c * (cellW + gap),
        y: topY + r * (cellH + gap),
        width: Math.max(updated[id].minWidth, cellW),
        height: Math.max(updated[id].minHeight, cellH),
        maximized: false
      };
    });
  }

  return updated;
}

function spawn(id: WindowId, z: number): WindowState {
  const def = WINDOW_REGISTRY[id];
  const px = def.defaultPos?.x ?? 120;
  const py = def.defaultPos?.y ?? 100;
  const x = px < 0 ? Math.max(16, vw() + px) : px;
  const y = py + def.defaultSize.height > vh() - TASKBAR_HEIGHT ? Math.max(NAVBAR_HEIGHT + 12, vh() - TASKBAR_HEIGHT - def.defaultSize.height - 16) : py;
  return {
    id, title: def.title,
    x: Math.min(x, Math.max(16, vw() - def.defaultSize.width - 16)),
    y,
    width: def.defaultSize.width, height: def.defaultSize.height,
    minWidth: def.minSize.width, minHeight: def.minSize.height,
    zIndex: z, minimized: false, maximized: false, visible: true, pin: "none"
  };
}

export const useWindowStore = create<Store>()(
  persist(
    (set, get) => ({
      windows: {},
      order: [],
      top: 10,
      hydrated: false,
      activeId: null,

      openWindow: (id) =>
        set((s) => {
          const z = s.top + 1;
          const existing = s.windows[id];
          const w = existing
            ? { ...existing, visible: true, minimized: false, zIndex: z }
            : spawn(id, z);
          const nextWindows = { ...s.windows, [id]: w };
          const nextOrder = s.order.includes(id) ? s.order : [...s.order, id];
          const arranged = computeAutoLayout(nextWindows, nextOrder, z);
          return {
            windows: arranged,
            order: nextOrder,
            top: z,
            activeId: id
          };
        }),

      toggleWindow: (id) => {
        const w = get().windows[id];
        if (w?.visible && !w.minimized && get().activeId === id) get().closeWindow(id);
        else get().openWindow(id);
      },

      closeWindow: (id) =>
        set((s) => {
          const windows = s.windows[id] ? { ...s.windows, [id]: { ...s.windows[id], visible: false } } : s.windows;
          const arranged = computeAutoLayout(windows, s.order, s.top);
          return {
            windows: arranged,
            activeId: s.activeId === id ? null : s.activeId
          };
        }),

      focusWindow: (id) =>
        set((s) => {
          if (!s.windows[id]) return s;
          if (s.activeId === id && s.windows[id].zIndex === s.top) return s;
          const z = s.top + 1;
          return { windows: { ...s.windows, [id]: { ...s.windows[id], zIndex: z } }, top: z, activeId: id };
        }),

      moveWindow: (id, x, y) =>
        set((s) => (s.windows[id] ? { windows: { ...s.windows, [id]: { ...s.windows[id], x, y } } } : s)),

      resizeWindow: (id, r) =>
        set((s) => (s.windows[id] ? { windows: { ...s.windows, [id]: { ...s.windows[id], ...r } } } : s)),

      minimizeWindow: (id) =>
        set((s) => ({ windows: { ...s.windows, [id]: { ...s.windows[id], minimized: true } }, activeId: null })),

      maximizeWindow: (id) =>
        set((s) => {
          const w = s.windows[id];
          if (!w) return s;
          if (w.maximized) {
            const r = w.restore ?? { x: 120, y: 100, width: w.minWidth + 120, height: w.minHeight + 120 };
            return { windows: { ...s.windows, [id]: { ...w, ...r, maximized: false, restore: undefined } } };
          }
          return {
            windows: {
              ...s.windows,
              [id]: {
                ...w, maximized: true, pin: "none",
                restore: { x: w.x, y: w.y, width: w.width, height: w.height },
                x: 0, y: NAVBAR_HEIGHT, width: vw(), height: vh() - NAVBAR_HEIGHT - TASKBAR_HEIGHT
              }
            }
          };
        }),

      restoreWindow: (id) =>
        set((s) => ({ windows: { ...s.windows, [id]: { ...s.windows[id], minimized: false, maximized: false, pin: "none" } }, activeId: id })),

      pinWindow: (id, pin) =>
        set((s) => {
          const w = s.windows[id];
          if (!w) return s;
          if (pin === "none") {
            const r = w.restore ?? { x: 160, y: 120, width: w.width, height: w.height };
            return { windows: { ...s.windows, [id]: { ...w, pin, ...r, restore: undefined } } };
          }
          const width = Math.max(w.minWidth, Math.min(w.width, 420));
          return {
            windows: {
              ...s.windows,
              [id]: {
                ...w, pin, maximized: false,
                restore: w.restore ?? { x: w.x, y: w.y, width: w.width, height: w.height },
                x: pin === "left" ? 0 : vw() - width,
                y: NAVBAR_HEIGHT,
                width,
                height: vh() - NAVBAR_HEIGHT - TASKBAR_HEIGHT
              }
            }
          };
        }),

      resetWindow: (id) => set((s) => ({ windows: { ...s.windows, [id]: spawn(id, s.top + 1) }, top: s.top + 1 })),

      applyPreset: (name) => {
        const ids = PRESETS[name] ?? [];
        set((s) => {
          const windows = { ...s.windows };
          for (const key of Object.keys(windows)) windows[key] = { ...windows[key], visible: false };
          let z = s.top;
          const order = [...s.order];
          ids.forEach((id) => {
            z += 1;
            windows[id] = spawn(id, z);
            if (!order.includes(id)) order.push(id);
          });
          const arranged = computeAutoLayout(windows, order, z);
          return { windows: arranged, order, top: z, activeId: ids[ids.length - 1] ?? null };
        });
      },

      autoArrangeWindows: () =>
        set((s) => ({
          windows: computeAutoLayout(s.windows, s.order, s.top)
        })),

      closeAll: () =>
        set((s) => {
          const windows = { ...s.windows };
          for (const key of Object.keys(windows)) windows[key] = { ...windows[key], visible: false };
          return { windows, activeId: null };
        }),

      setHydrated: () => set({ hydrated: true })
    }),
    {
      name: "nagarx.workspace.layout.v1",
      partialize: (s) => ({ windows: s.windows, order: s.order, top: s.top }) as any,
      onRehydrateStorage: () => (state) => state?.setHydrated()
    }
  )
);
