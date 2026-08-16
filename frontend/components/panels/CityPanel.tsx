"use client";
import { CITY } from "@/lib/city-model";
import { KV, SectionTitle } from "@/components/ui/Bits";
import { useMapStore } from "@/stores/map-store";
import { num } from "@/lib/format";

export default function CityPanel() {
  const demo = useMapStore((s) => s.demo);
  return (
    <div>
      <div style={{ fontSize: 16, marginBottom: 2 }}>{CITY.name}</div>
      <div className="muted" style={{ marginBottom: 10 }}>{CITY.state} · pilot sector</div>

      <SectionTitle>Dataset</SectionTitle>
      <KV k="Dataset version" v={CITY.datasetVersion} />
      <KV k="CRS" v={CITY.crs} />
      <KV k="Last ingest" v={CITY.updatedAt} />
      <KV k="Source" v={demo ? "Local demo engine" : "Backend API"} />

      <SectionTitle>Metrics</SectionTitle>
      <KV k="Area" v={CITY.areaKm2 + " km²"} />
      <KV k="Population" v={num(CITY.population)} />
      <KV k="Households" v={num(CITY.households)} />
      <KV k="Wards" v={CITY.wards} />
      <KV k="Centre" v={CITY.center.lat.toFixed(4) + ", " + CITY.center.lon.toFixed(4)} />
    </div>
  );
}
