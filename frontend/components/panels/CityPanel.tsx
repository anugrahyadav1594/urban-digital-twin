"use client";
import { useEffect, useState } from "react";
import { CITY } from "@/lib/city-model";
import { KV, SectionTitle } from "@/components/ui/Bits";
import { useMapStore } from "@/stores/map-store";
import { num } from "@/lib/format";
import { api } from "@/lib/api/client";
import type { CityInfo } from "@/types";

/**
 * City summary.
 *
 * Reads GET /city so the figures are the live PostGIS totals. CITY stays as
 * the offline fallback only; when it is in use the Source row says so and the
 * global DEMO DATA banner is showing.
 */
export default function CityPanel() {
  const demo = useMapStore((s) => s.demo);
  const [city, setCity] = useState<CityInfo>(CITY);

  useEffect(() => {
    let alive = true;
    api.getCity().then((c) => { if (alive && c) setCity(c); });
    return () => { alive = false; };
  }, []);

  const counts = (city as CityInfo & { counts?: Record<string, number> }).counts;

  return (
    <div>
      <div style={{ fontSize: 16, marginBottom: 2 }}>{city.name}</div>
      <div className="muted" style={{ marginBottom: 10 }}>{city.state} · pilot sector</div>

      <SectionTitle>Dataset</SectionTitle>
      <KV k="Dataset version" v={city.datasetVersion} />
      <KV k="CRS" v={city.crs} />
      <KV k="Last ingest" v={String(city.updatedAt).slice(0, 19).replace("T", " ")} />
      <KV k="Source" v={demo ? "Local demo engine" : "Backend API · PostGIS"} />

      <SectionTitle>Metrics</SectionTitle>
      <KV k="Area" v={city.areaKm2 + " km²"} />
      <KV k="Population" v={num(city.population)} />
      <KV k="Households" v={num(city.households)} />
      <KV k="Wards" v={city.wards} />
      <KV k="Centre" v={city.center.lat.toFixed(4) + ", " + city.center.lon.toFixed(4)} />

      {counts && (
        <>
          <SectionTitle>Features in database</SectionTitle>
          {Object.entries(counts)
            .filter(([, v]) => v > 0)
            .sort((a, b) => b[1] - a[1])
            .map(([k, v]) => (
              <KV key={k} k={k.replace(/_/g, " ")} v={num(v)} />
            ))}
        </>
      )}
    </div>
  );
}
