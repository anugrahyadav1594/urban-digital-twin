"use client";
import dynamic from "next/dynamic";
import { useEffect } from "react";
import TopNavbar from "./TopNavbar";
import WindowManager from "./WindowManager";
import Taskbar from "./Taskbar";
import CommandPalette from "./CommandPalette";
import { useWindowStore } from "@/stores/window-store";

/* Cesium touches window/WebGL - never render it on the server. */
const CesiumViewer = dynamic(() => import("@/cesium/CesiumViewer"), {
  ssr: false,
  loading: () => <div className="cesium-fallback">initialising 3d city…</div>
});

export default function Workspace() {
  const { hydrated, order, openWindow } = useWindowStore();

  // First visit: open the default workspace preset.
  useEffect(() => {
    if (!hydrated) return;
    if (order.length === 0) {
      openWindow("layers");
      openWindow("inspector");
    }
  }, [hydrated, order.length, openWindow]);

  return (
    <div className="workspace">
      <CesiumViewer />
      <TopNavbar />
      <WindowManager />
      <Taskbar />
      <CommandPalette />
    </div>
  );
}
