"use client";
import { useSelectionStore } from "@/stores/selection-store";
import { useWindowStore } from "@/stores/window-store";
import { mapBridge } from "@/cesium/map-bridge";
import { KV, SectionTitle, Empty } from "@/components/ui/Bits";

export default function InspectorPanel() {
  const { feature, loading, history, select } = useSelectionStore();
  const openWindow = useWindowStore((s) => s.openWindow);

  if (loading) return <Empty><span className="pulse">resolving feature…</span></Empty>;
  if (!feature)
    return (
      <Empty>
        Click any building, parcel or facility in the 3D city.
        <br />
        <span className="mono" style={{ fontSize: 11 }}>selection → GET /features/&#123;id&#125;</span>
      </Empty>
    );

  return (
    <div>
      <div className="row">
        <div>
          <div style={{ fontSize: 15 }}>{feature.name}</div>
          <div className="mono muted" style={{ fontSize: 11 }}>{feature.id} · {feature.kind}</div>
        </div>
        <span className="chip info">{feature.kind}</span>
      </div>

      <div style={{ display: "flex", gap: 6, margin: "10px 0" }}>
        <button className="btn" style={{ flex: 1 }} onClick={() => mapBridge.flyTo(feature.id)}>Fly to</button>
        <button className="btn ghost" style={{ flex: 1 }} onClick={() => { mapBridge.highlight([feature.id]); openWindow("planning"); }}>Use in plan</button>
      </div>

      <SectionTitle>Attributes</SectionTitle>
      {Object.entries(feature.attributes).map(([k, v]) => <KV key={k} k={k} v={String(v)} />)}

      <SectionTitle>Position</SectionTitle>
      <KV k="Longitude" v={feature.position.lon.toFixed(5)} />
      <KV k="Latitude" v={feature.position.lat.toFixed(5)} />

      {history.length > 1 && (
        <>
          <SectionTitle>Recent selections</SectionTitle>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
            {history.slice(1).map((h) => (
              <button key={h} className="chip" onClick={() => { select(h); mapBridge.flyTo(h); }}>{h}</button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
