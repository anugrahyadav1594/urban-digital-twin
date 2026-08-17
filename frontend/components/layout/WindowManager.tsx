"use client";
import { useEffect } from "react";
import FloatingWindow from "@/components/windows/FloatingWindow";
import { WINDOW_CONTENT } from "@/components/windows/registry";
import { useWindowStore, type WindowId } from "@/stores/window-store";

export default function WindowManager() {
  const { windows, order, activeId, closeWindow, openWindow, hydrated } = useWindowStore();

  /* keyboard shortcuts */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (e.key === "Escape" && activeId) { closeWindow(activeId); return; }
      if (!mod) return;
      const map: Record<string, WindowId> = { "1": "layers", "2": "planning", "3": "analysis", "4": "scenario", "5": "ai", "6": "comparison" };
      if (map[e.key]) { e.preventDefault(); openWindow(map[e.key]); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [activeId, closeWindow, openWindow]);

  if (!hydrated) return null;

  return (
    <>
      {order.map((id) => {
        const win = windows[id];
        const Content = WINDOW_CONTENT[id];
        if (!win || !win.visible || !Content) return null;
        return (
          <FloatingWindow key={id} win={win}>
            <Content />
          </FloatingWindow>
        );
      })}
    </>
  );
}
