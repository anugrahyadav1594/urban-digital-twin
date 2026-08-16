"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { NAVBAR_HEIGHT, TASKBAR_HEIGHT } from "@/lib/constants";
import { clamp } from "@/lib/format";
import { WINDOW_REGISTRY, useWindowStore, type WindowId, type WindowState } from "@/stores/window-store";

type Handle = "n" | "s" | "e" | "w" | "nw" | "ne" | "sw" | "se";
const HANDLES: Handle[] = ["n", "s", "e", "w", "nw", "ne", "sw", "se"];
const SNAP_EDGE = 22;

type Ghost = { x: number; y: number; width: number; height: number } | null;

export default function FloatingWindow({ win, children }: { win: WindowState; children: React.ReactNode }) {
  const { focusWindow, moveWindow, resizeWindow, closeWindow, minimizeWindow, maximizeWindow, pinWindow, resetWindow, activeId } = useWindowStore();
  const [drag, setDrag] = useState(false);
  const [ghost, setGhost] = useState<Ghost>(null);
  const [menu, setMenu] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const focused = activeId === win.id;
  const icon = WINDOW_REGISTRY[win.id]?.icon ?? "◈";

  /* ── dragging via the title bar ─────────────────────────────── */
  const onTitlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      if ((e.target as HTMLElement).closest(".wbtn")) return;
      if (win.maximized) return;
      focusWindow(win.id);
      const startX = e.clientX, startY = e.clientY;
      const ox = win.x, oy = win.y;
      const maxY = window.innerHeight - TASKBAR_HEIGHT - 34;
      setDrag(true);
      (e.target as HTMLElement).setPointerCapture?.(e.pointerId);

      const move = (ev: PointerEvent) => {
        const nx = clamp(ox + ev.clientX - startX, -win.width + 90, window.innerWidth - 90);
        const ny = clamp(oy + ev.clientY - startY, NAVBAR_HEIGHT, maxY);
        moveWindow(win.id, nx, ny);

        // edge snapping preview
        const h = window.innerHeight - NAVBAR_HEIGHT - TASKBAR_HEIGHT;
        if (ev.clientY <= NAVBAR_HEIGHT + 4) setGhost({ x: 0, y: NAVBAR_HEIGHT, width: window.innerWidth, height: h });
        else if (ev.clientX <= SNAP_EDGE) setGhost({ x: 0, y: NAVBAR_HEIGHT, width: Math.round(window.innerWidth / 2), height: h });
        else if (ev.clientX >= window.innerWidth - SNAP_EDGE)
          setGhost({ x: Math.round(window.innerWidth / 2), y: NAVBAR_HEIGHT, width: Math.round(window.innerWidth / 2), height: h });
        else setGhost(null);
      };

      const up = () => {
        setDrag(false);
        setGhost((g) => {
          if (g) resizeWindow(win.id, g);
          return null;
        });
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", up);
      };

      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", up);
    },
    [win, focusWindow, moveWindow, resizeWindow]
  );

  /* ── resizing from the 8 handles ────────────────────────────── */
  const onResizeDown = useCallback(
    (e: React.PointerEvent, h: Handle) => {
      e.stopPropagation();
      focusWindow(win.id);
      const sx = e.clientX, sy = e.clientY;
      const o = { x: win.x, y: win.y, width: win.width, height: win.height };

      const move = (ev: PointerEvent) => {
        const dx = ev.clientX - sx, dy = ev.clientY - sy;
        let { x, y, width, height } = o;
        if (h.includes("e")) width = Math.max(win.minWidth, o.width + dx);
        if (h.includes("s")) height = Math.max(win.minHeight, o.height + dy);
        if (h.includes("w")) { width = Math.max(win.minWidth, o.width - dx); x = o.x + (o.width - width); }
        if (h.includes("n")) { height = Math.max(win.minHeight, o.height - dy); y = Math.max(NAVBAR_HEIGHT, o.y + (o.height - height)); }
        resizeWindow(win.id, { x, y, width, height });
      };
      const up = () => {
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", up);
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", up);
    },
    [win, focusWindow, resizeWindow]
  );

  useEffect(() => {
    if (!menu) return;
    const close = () => setMenu(false);
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, [menu]);

  if (!win.visible || win.minimized) return null;

  return (
    <>
      {ghost && <div className="snap-ghost" style={{ left: ghost.x, top: ghost.y, width: ghost.width, height: ghost.height }} />}
      <div
        ref={ref}
        className={"fwin" + (focused ? " focused" : "") + (drag ? " dragging" : "")}
        style={{
          left: win.x,
          top: win.y,
          width: win.width,
          height: win.height,
          zIndex: win.zIndex,
          transition: drag ? "none" : "left 0.32s cubic-bezier(0.16, 1, 0.3, 1), top 0.32s cubic-bezier(0.16, 1, 0.3, 1), width 0.32s cubic-bezier(0.16, 1, 0.3, 1), height 0.32s cubic-bezier(0.16, 1, 0.3, 1)"
        }}
        onPointerDown={() => focusWindow(win.id)}
      >
        <div className="fwin-title" onPointerDown={onTitlePointerDown} onDoubleClick={() => maximizeWindow(win.id)}>
          <span className="glyph">{icon}</span>
          <span className="label">{win.title}</span>

          <button className="wbtn" title="Window menu" onClick={(e) => { e.stopPropagation(); setMenu((m) => !m); }}>&#8942;</button>
          <button className="wbtn" title="Minimize" onClick={() => minimizeWindow(win.id)}>&#8211;</button>
          <button className="wbtn" title={win.maximized ? "Restore" : "Maximize"} onClick={() => maximizeWindow(win.id)}>{win.maximized ? "❐" : "□"}</button>
          <button className="wbtn close" title="Close" onClick={() => closeWindow(win.id)}>&#215;</button>

          {menu && (
            <div className="menu" style={{ right: 4, left: "auto", top: 30 }} onClick={(e) => e.stopPropagation()}>
              <div className="sec">Window</div>
              <button onClick={() => { resetWindow(win.id); setMenu(false); }}>Reset position &amp; size</button>
              <button onClick={() => { pinWindow(win.id, win.pin === "left" ? "none" : "left"); setMenu(false); }}>
                {win.pin === "left" ? "Unpin from left" : "Pin left"}
              </button>
              <button onClick={() => { pinWindow(win.id, win.pin === "right" ? "none" : "right"); setMenu(false); }}>
                {win.pin === "right" ? "Unpin from right" : "Pin right"}
              </button>
              <button onClick={() => { maximizeWindow(win.id); setMenu(false); }}>{win.maximized ? "Restore" : "Maximize"}</button>
              <button onClick={() => { closeWindow(win.id); setMenu(false); }}>Close<span className="kbd">Esc</span></button>
            </div>
          )}
        </div>

        <div className={"fwin-body" + (win.id === "ai" ? " flush" : "")}>{children}</div>

        {!win.maximized && HANDLES.map((h) => <div key={h} className={"rh rh-" + h} onPointerDown={(e) => onResizeDown(e, h)} />)}
      </div>
    </>
  );
}
