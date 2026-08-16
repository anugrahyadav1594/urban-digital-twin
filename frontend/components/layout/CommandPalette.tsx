"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { PRESETS, WINDOW_REGISTRY, useWindowStore, type WindowId } from "@/stores/window-store";
import { mapBridge } from "@/cesium/map-bridge";
import { PARCELS } from "@/lib/city-model";
import { useSelectionStore } from "@/stores/selection-store";

type Cmd = { label: string; hint: string; run: () => void };

export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [i, setI] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const { openWindow, applyPreset, closeAll } = useWindowStore();
  const select = useSelectionStore((s) => s.select);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen((o) => !o); setQ(""); setI(0); }
      if (e.key === "Escape") setOpen(false);
    };
    const onEvt = () => { setOpen(true); setQ(""); setI(0); };
    window.addEventListener("keydown", onKey);
    window.addEventListener("nagarx:palette", onEvt as EventListener);
    return () => { window.removeEventListener("keydown", onKey); window.removeEventListener("nagarx:palette", onEvt as EventListener); };
  }, []);

  useEffect(() => { if (open) setTimeout(() => inputRef.current?.focus(), 10); }, [open]);

  const commands: Cmd[] = useMemo(() => {
    const list: Cmd[] = (Object.keys(WINDOW_REGISTRY) as WindowId[]).map((id) => ({
      label: "Open · " + WINDOW_REGISTRY[id].title,
      hint: "window",
      run: () => openWindow(id)
    }));
    Object.keys(PRESETS).forEach((p) => list.push({ label: "Workspace · " + p, hint: "preset", run: () => applyPreset(p) }));
    list.push({ label: "Close all windows", hint: "layout", run: () => closeAll() });
    list.push({ label: "Shortest route home · City overview", hint: "camera", run: () => mapBridge.home() });
    list.push({ label: "Set Top-down view at current map location", hint: "camera", run: () => mapBridge.topDown() });
    list.push({ label: "Set 3D Perspective view at current map location", hint: "camera", run: () => mapBridge.perspectiveView() });

    const idQuery = q.replace(/[^0-9]/g, "");
    if (idQuery.length >= 3) {
      PARCELS.filter((p) => p.id.includes(idQuery)).slice(0, 6).forEach((p) =>
        list.unshift({
          label: "Parcel #" + p.id.split("_")[1] + " · " + p.ward + " · " + p.zoning,
          hint: "feature",
          run: () => { select(p.id); mapBridge.flyTo(p.id); openWindow("inspector"); }
        })
      );
    }
    return list;
  }, [q, openWindow, applyPreset, closeAll, select]);

  const filtered = commands.filter((c) => c.label.toLowerCase().includes(q.toLowerCase())).slice(0, 12);

  if (!open) return null;

  return (
    <div className="palette-backdrop" onClick={() => setOpen(false)}>
      <div className="palette" onClick={(e) => e.stopPropagation()}>
        <input
          ref={inputRef}
          placeholder="Search windows, presets, camera actions, parcel ids…"
          value={q}
          onChange={(e) => { setQ(e.target.value); setI(0); }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") setI((v) => Math.min(v + 1, filtered.length - 1));
            if (e.key === "ArrowUp") setI((v) => Math.max(v - 1, 0));
            if (e.key === "Enter" && filtered[i]) { filtered[i].run(); setOpen(false); }
          }}
        />
        <div className="list">
          {filtered.map((c, idx) => (
            <div key={c.label} className={"item" + (idx === i ? " on" : "")} onMouseEnter={() => setI(idx)} onClick={() => { c.run(); setOpen(false); }}>
              <span>{c.label}</span>
              <span className="hint">{c.hint}</span>
            </div>
          ))}
          {filtered.length === 0 && <div className="item muted">no matches</div>}
        </div>
      </div>
    </div>
  );
}
