"use client";
import { useLayerStore } from "@/stores/layer-store";
import { useWindowStore } from "@/stores/window-store";
import { SectionTitle } from "@/components/ui/Bits";
import type { Layer } from "@/types";

const GROUPS: Layer["group"][] = ["Base", "Semantic", "Risk", "Planning"];

export default function LayersPanel() {
  const { layers, setVisible, setOpacity, reset } = useLayerStore();
  const openWindow = useWindowStore((s) => s.openWindow);

  return (
    <div>
      <div className="row" style={{ marginBottom: 8 }}>
        <span className="muted mono" style={{ fontSize: 11 }}>{layers.filter((l) => l.visible).length}/{layers.length} visible</span>
        <div style={{ display: "flex", gap: 6 }}>
          <button className="btn ghost" style={{ padding: "3px 8px" }} onClick={() => openWindow("legend")}>Legend</button>
          <button className="btn ghost" style={{ padding: "3px 8px" }} onClick={reset}>Reset</button>
        </div>
      </div>

      {GROUPS.map((g) => (
        <div key={g} style={{ marginBottom: 10 }}>
          <SectionTitle>{g}</SectionTitle>
          {layers.filter((l) => l.group === g).map((l) => (
            <div key={l.id}>
              <div className="layer-row">
                <input type="checkbox" checked={l.visible} onChange={(e) => setVisible(l.id, e.target.checked)} />
                <span className="swatch" style={{ background: l.color }} />
                <span style={{ flex: 1, fontSize: 12 }}>{l.name}</span>
                <span className="muted mono" style={{ fontSize: 10.5 }}>{l.count}</span>
              </div>
              {l.visible && (
                <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "0 4px 6px 26px" }}>
                  <input type="range" min={5} max={100} value={Math.round(l.opacity * 100)} style={{ flex: 1 }}
                    onChange={(e) => setOpacity(l.id, Number(e.target.value) / 100)} />
                  <span className="mono muted" style={{ fontSize: 10, width: 30, textAlign: "right" }}>{Math.round(l.opacity * 100)}%</span>
                </div>
              )}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
