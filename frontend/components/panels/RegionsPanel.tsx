"use client";
/**
 * Comparison regions.
 *
 * The batch extractor produced four study areas but only the pilot sector
 * (Adivali-devad) was ever drawn, because the per-region tables had no route
 * on the main API. This panel lists all four and switches the globe between
 * them.
 *
 * Display only: the analysis, scenario and emergency engines still operate on
 * the pilot sector's canonical tables. Selecting another region shows its
 * geometry; it does not repoint those tools.
 */
import { useEffect, useState } from "react";
import { mapBridge } from "@/cesium/map-bridge";
import { listRegions, type RegionInfo } from "@/cesium/regionData";
import { SectionTitle, Empty } from "@/components/ui/Bits";

const LAYER_COLOR: Record<string, string> = {
  roads: "#94a3b8",
  buildings: "#cbd5e1",
  water: "#0ea5e9",
  bridges: "#f59e0b",
};

const PILOT = "adivali_devad";

export default function RegionsPanel() {
  const [regions, setRegions] = useState<RegionInfo[] | null>(null);
  const [active, setActive] = useState<string>(PILOT);
  const [busy, setBusy] = useState<string | null>(null);
  const [drawn, setDrawn] = useState<Record<string, number>>({});
  const [status, setStatus] = useState<Record<string, string>>({});
  const [hidden, setHidden] = useState<Record<string, boolean>>({});
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    listRegions().then((r) => {
      if (!alive) return;
      setRegions(r);
      if (r.length === 0) setErr("Backend unreachable - cannot list regions.");
    });
    return () => {
      alive = false;
    };
  }, []);

  async function select(r: RegionInfo) {
    if (busy) return;
    setBusy(r.id);
    setErr(null);
    setHidden({});
    try {
      const res = await mapBridge.showRegion(r.id);
      setActive(r.id);
      setDrawn(res.counts ?? {});
      setStatus(res.status ?? {});
      if (!res.total) {
        setErr(
          r.available
            ? "Region has rows but nothing drawable was returned."
            : `No extracted data for ${r.label}. Run the batch extractor for this region.`
        );
      }
    } catch (e: any) {
      setErr(e?.message ?? "Failed to load region.");
    } finally {
      setBusy(null);
    }
  }

  function back() {
    mapBridge.clearRegion();
    setActive(PILOT);
    setDrawn({});
    setStatus({});
    setHidden({});
    setErr(null);
  }

  function toggleLayer(layer: string) {
    const next = !hidden[layer];
    setHidden({ ...hidden, [layer]: next });
    mapBridge.setRegionLayerVisible(layer, !next);
  }

  if (regions === null) return <Empty>Loading regions…</Empty>;
  if (regions.length === 0)
    return <Empty>{err ?? "No regions returned by the API."}</Empty>;

  const current = regions.find((r) => r.id === active);
  const showingRemote = active !== PILOT && Object.keys(drawn).length > 0;

  return (
    <div>
      <SectionTitle>Study areas</SectionTitle>
      <div className="muted" style={{ fontSize: 11, marginBottom: 8 }}>
        Geometry only — analysis tools stay on the pilot sector.
      </div>

      {regions.map((r) => {
        const isActive = r.id === active;
        const loading = busy === r.id;
        return (
          <button
            key={r.id}
            onClick={() => select(r)}
            disabled={!!busy}
            style={{
              display: "block",
              width: "100%",
              textAlign: "left",
              marginBottom: 6,
              padding: "8px 10px",
              borderRadius: 6,
              cursor: busy ? "default" : "pointer",
              border: isActive
                ? "1px solid rgba(56,189,248,0.75)"
                : "1px solid rgba(148,163,184,0.25)",
              background: isActive
                ? "rgba(56,189,248,0.12)"
                : "rgba(148,163,184,0.06)",
              color: "inherit",
              opacity: r.available ? 1 : 0.55,
            }}
          >
            <div className="row" style={{ justifyContent: "space-between" }}>
              <span style={{ fontSize: 12, fontWeight: 600 }}>{r.label}</span>
              <span className="mono muted" style={{ fontSize: 10 }}>
                {loading
                  ? "loading…"
                  : r.available
                  ? `${r.featureCount.toLocaleString()} feat`
                  : "no data"}
              </span>
            </div>
            {r.note && (
              <div className="muted" style={{ fontSize: 10, marginTop: 2 }}>
                {r.note}
              </div>
            )}
            {!r.available && (
              <div style={{ fontSize: 10, marginTop: 3, color: "#f59e0b" }}>
                Not extracted yet
              </div>
            )}
          </button>
        );
      })}

      {err && (
        <div
          style={{
            marginTop: 8,
            padding: "7px 9px",
            borderRadius: 6,
            fontSize: 11,
            background: "rgba(245,158,11,0.12)",
            border: "1px solid rgba(245,158,11,0.4)",
            color: "#fbbf24",
          }}
        >
          {err}
        </div>
      )}

      {showingRemote && (
        <>
          <SectionTitle>Drawn — {current?.label}</SectionTitle>
          {Object.entries(drawn).map(([layer, n]) => (
            <div
              key={layer}
              className="row"
              style={{ justifyContent: "space-between", padding: "3px 0" }}
            >
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  fontSize: 11,
                  cursor: "pointer",
                }}
              >
                <input
                  type="checkbox"
                  checked={!hidden[layer]}
                  onChange={() => toggleLayer(layer)}
                />
                <span
                  style={{
                    width: 9,
                    height: 9,
                    borderRadius: 2,
                    background: LAYER_COLOR[layer] ?? "#94a3b8",
                    display: "inline-block",
                  }}
                />
                {layer}
              </label>
              <span className="mono muted" style={{ fontSize: 10 }}>
                {n.toLocaleString()}
              </span>
            </div>
          ))}

          {Object.entries(status).some(([, v]) => !/^\d+ features$/.test(v)) && (
            <div className="muted" style={{ fontSize: 10, marginTop: 6 }}>
              {Object.entries(status)
                .filter(([, v]) => !/^\d+ features$/.test(v))
                .map(([k, v]) => `${k}: ${v}`)
                .join(" · ")}
            </div>
          )}

          <button
            className="btn ghost"
            style={{ marginTop: 10, width: "100%" }}
            onClick={back}
          >
            Back to pilot sector
          </button>
        </>
      )}
    </div>
  );
}