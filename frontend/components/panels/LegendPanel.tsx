"use client";
import { useLayerStore } from "@/stores/layer-store";
import { SectionTitle, Empty } from "@/components/ui/Bits";

export default function LegendPanel() {
  const layers = useLayerStore((s) => s.layers).filter((l) => l.visible && l.legend);
  if (layers.length === 0) return <Empty>Enable a thematic layer (land use, population, flood risk) to see its legend.</Empty>;

  return (
    <div>
      {layers.map((l) => (
        <div key={l.id} style={{ marginBottom: 12 }}>
          <SectionTitle>{l.name}</SectionTitle>
          {l.legend!.map((e) => (
            <div key={e.label} className="layer-row" style={{ padding: "3px 4px" }}>
              <span className="swatch" style={{ background: e.color, width: 14, height: 10 }} />
              <span style={{ fontSize: 12 }}>{e.label}</span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
