"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { mapBridge } from "@/cesium/map-bridge";
import { useMapStore } from "@/stores/map-store";
import { useScenarioStore } from "@/stores/scenario-store";
import { Field, SectionTitle } from "@/components/ui/Bits";

type Hazard = { id: string; label: string; defaultRadiusM: number; responderType: string };
type Measure = {
  id: string; label: string; reduces: string; effect: number;
  appliesTo: string[]; note: string;
};

const fmtMin = (s: number | undefined) =>
  s === undefined || s === null ? "—" : `${s.toFixed(2)} min`;

/** Row of a before/after comparison table. */
function DeltaRow({ label, a, b, unit }: { label: string; a?: number; b?: number; unit?: string }) {
  if (a === undefined || b === undefined) return null;
  const delta = b - a;
  const pct = a ? (100 * delta) / a : 0;
  const good = delta < 0;
  return (
    <div className="row" style={{ fontSize: 11.5, padding: "3px 0" }}>
      <span style={{ flex: 1 }}>{label}</span>
      <span className="mono" style={{ width: 74, textAlign: "right", color: "var(--txt-dim)" }}>
        {a.toLocaleString()}{unit}
      </span>
      <span className="mono" style={{ width: 18, textAlign: "center", color: "var(--txt-dim)" }}>→</span>
      <span className="mono" style={{ width: 74, textAlign: "right" }}>{b.toLocaleString()}{unit}</span>
      <span className="mono" style={{ width: 56, textAlign: "right", color: good ? "var(--good)" : delta > 0 ? "var(--bad)" : "var(--txt-dim)" }}>
        {delta === 0 ? "—" : `${pct > 0 ? "+" : ""}${pct.toFixed(0)}%`}
      </span>
    </div>
  );
}

export default function EmergencyPanel() {
  const [tab, setTab] = useState<"route" | "disaster">("route");
  const [cat, setCat] = useState<{ hazards: Hazard[]; measures: Measure[] }>({ hazards: [], measures: [] });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Incident location. Defaults to the city centre; "pick on map" overwrites it.
  const [lon, setLon] = useState(73.135);
  const [lat, setLat] = useState(19.002);

  const [responder, setResponder] = useState("fire_station");
  const [targetMin, setTargetMin] = useState(8);
  const [turnout, setTurnout] = useState(60);
  const [routes, setRoutes] = useState<any[] | null>(null);

  const [hazardType, setHazardType] = useState("fire");
  const [radius, setRadius] = useState<number | "">("");
  const [intensity, setIntensity] = useState(1.0);
  const [measures, setMeasures] = useState<string[]>([]);
  const [sim, setSim] = useState<any | null>(null);

  const activeScenario = useScenarioStore((s) => s.scenarios.find((x) => x.id === s.activeId));
  const picked = useMapStore((s) => s.lastClick);

  useEffect(() => {
    api.emergencyCatalogue().then((c) => {
      setCat(c);
      if (c?.hazards?.length && !c.hazards.find((h: Hazard) => h.id === hazardType)) {
        setHazardType(c.hazards[0].id);
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // If the map store exposes a last-clicked coordinate, offer it as the incident.
  useEffect(() => {
    if (picked && typeof picked.lon === "number" && typeof picked.lat === "number") {
      setLon(Number(picked.lon.toFixed(6)));
      setLat(Number(picked.lat.toFixed(6)));
    }
  }, [picked]);

  const hazardSpec = cat.hazards.find((h) => h.id === hazardType);
  const applicable = (m: Measure) => !m.appliesTo.length || m.appliesTo.includes(hazardType);

  const toggleMeasure = (id: string) =>
    setMeasures((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  const runRoute = async () => {
    setBusy(true); setErr(null); setSim(null);
    try {
      const out = await api.emergencyRoute({
        lon, lat, responderType: responder, topN: 3,
        turnoutSeconds: turnout, responseTargetSeconds: targetMin * 60,
        scenario_id: activeScenario?.id
      });
      if (!out) { setErr("Backend unreachable or no route data returned."); setRoutes(null); return; }
      const recs = out.records ?? [];
      setRoutes(recs);
      mapBridge.showHazard({ center: [lon, lat], label: "Incident" });
      mapBridge.showEmergencyRoutes(recs.map((r: any) => ({
        stationId: r.station_id, stationName: r.station_name, path: r.path,
        responseTimeMin: r.response_time_min, isPrimary: r.is_primary,
        withinTarget: r.within_target
      })));
      if (out.warnings?.length) setErr(out.warnings.join(" "));
    } catch (e: any) {
      setErr(String(e?.message ?? e));
    } finally { setBusy(false); }
  };

  const runSim = async () => {
    setBusy(true); setErr(null); setRoutes(null);
    try {
      const out = await api.simulateDisaster({
        hazardType, lon, lat,
        radiusM: radius === "" ? null : Number(radius),
        intensity, measures,
        responseTargetSeconds: targetMin * 60,
        includeRouting: true,
        scenario_id: activeScenario?.id
      });
      if (!out) { setErr("Backend unreachable or simulation failed."); return; }
      setSim(out);
      mapBridge.showHazard({
        center: out.hazard.center, label: out.hazard.label,
        footprint: out.hazard.footprint,
        footprintMitigated: measures.length ? out.hazard.footprint_mitigated : null
      });
      const resp = out.response;
      const draw = resp?.with_measures ?? resp?.during_event ?? resp?.normal;
      if (draw?.path) {
        mapBridge.showEmergencyRoutes([{
          stationId: draw.station_id, stationName: draw.station_name,
          path: draw.path, responseTimeMin: draw.response_time_min,
          isPrimary: true, withinTarget: draw.within_target
        }]);
      } else {
        mapBridge.showEmergencyRoutes([]);
      }
    } catch (e: any) {
      setErr(String(e?.message ?? e));
    } finally { setBusy(false); }
  };

  const m = (r: any, key: string) => r?.metrics?.find((x: any) => x.name === key)?.value;

  return (
    <div>
      <div className="tabs">
        <button className={"tab" + (tab === "route" ? " on" : "")} onClick={() => setTab("route")}>Route finder</button>
        <button className={"tab" + (tab === "disaster" ? " on" : "")} onClick={() => setTab("disaster")}>Disaster simulator</button>
      </div>

      <SectionTitle>Incident location</SectionTitle>
      <div style={{ display: "flex", gap: 8 }}>
        <Field label="Longitude">
          <input className="input" type="number" step={0.0001} value={lon}
            onChange={(e) => setLon(Number(e.target.value))} />
        </Field>
        <Field label="Latitude">
          <input className="input" type="number" step={0.0001} value={lat}
            onChange={(e) => setLat(Number(e.target.value))} />
        </Field>
      </div>
      <div className="muted" style={{ fontSize: 10.5, marginTop: -4, marginBottom: 10 }}>
        Click the map to set this, or type coordinates directly.
      </div>

      {tab === "route" ? (
        <>
          <div style={{ display: "flex", gap: 8 }}>
            <Field label="Responding service">
              <select className="input" value={responder} onChange={(e) => setResponder(e.target.value)}>
                <option value="fire_station">Fire station</option>
                <option value="hospital">Hospital / ambulance</option>
                <option value="police">Police</option>
              </select>
            </Field>
            <Field label="Target (min)">
              <input className="input" type="number" min={1} max={60} value={targetMin}
                onChange={(e) => setTargetMin(Number(e.target.value))} />
            </Field>
          </div>
          <Field label="Turnout time (s) — dispatch to wheels rolling">
            <input className="input" type="number" min={0} max={600} step={15} value={turnout}
              onChange={(e) => setTurnout(Number(e.target.value))} />
          </Field>

          <button className="btn primary wide" disabled={busy} onClick={runRoute}>
            {busy ? "ROUTING…" : "FIND FASTEST UNITS"}
          </button>

          {routes && (
            <>
              <SectionTitle>Dispatch order</SectionTitle>
              {routes.length === 0 && (
                <div className="muted" style={{ fontSize: 11.5 }}>
                  No unit can reach this incident on the current network.
                </div>
              )}
              {routes.map((r: any) => (
                <div key={r.station_id} style={{
                  display: "flex", alignItems: "center", gap: 8, padding: "5px 7px",
                  marginBottom: 4, borderRadius: 4,
                  background: r.is_primary ? "rgba(0,229,255,.09)" : "transparent",
                  border: "1px solid " + (r.is_primary ? "rgba(0,229,255,.35)" : "var(--line)")
                }}>
                  <span className="mono" style={{ width: 16, color: "var(--txt-dim)" }}>{r.rank}</span>
                  <span style={{ flex: 1, fontSize: 11.5 }}>{r.station_name}</span>
                  <span className="mono" style={{ fontSize: 11.5, color: r.within_target ? "var(--good)" : "var(--bad)" }}>
                    {fmtMin(r.response_time_min)}
                  </span>
                  <span className="mono" style={{ fontSize: 10.5, width: 58, textAlign: "right", color: "var(--txt-dim)" }}>
                    {(r.distance_m / 1000).toFixed(2)} km
                  </span>
                </div>
              ))}
              <div className="muted" style={{ fontSize: 10.5, marginTop: 6 }}>
                Includes {turnout} turnout. Target {targetMin} minutes.
              </div>
            </>
          )}
        </>
      ) : (
        <>
          <div style={{ display: "flex", gap: 8 }}>
            <Field label="Hazard">
              <select className="input" value={hazardType}
                onChange={(e) => { setHazardType(e.target.value); setRadius(""); }}>
                {cat.hazards.map((h) => <option key={h.id} value={h.id}>{h.label}</option>)}
              </select>
            </Field>
            <Field label={`Radius (m)${hazardSpec ? ` — default ${hazardSpec.defaultRadiusM}` : ""}`}>
              <input className="input" type="number" min={50} step={50}
                placeholder={hazardSpec ? String(hazardSpec.defaultRadiusM) : "auto"}
                value={radius} onChange={(e) => setRadius(e.target.value === "" ? "" : Number(e.target.value))} />
            </Field>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <span style={{ fontSize: 11.5, flex: 1 }}>Intensity</span>
            <input type="range" min={0.1} max={1} step={0.05} value={intensity} style={{ width: 130 }}
              onChange={(e) => setIntensity(Number(e.target.value))} />
            <span className="mono" style={{ width: 34, textAlign: "right", fontSize: 11 }}>
              {intensity.toFixed(2)}
            </span>
          </div>

          <SectionTitle>Mitigation measures</SectionTitle>
          {cat.measures.map((ms) => {
            const ok = applicable(ms);
            return (
              <label key={ms.id} title={ms.note}
                style={{
                  display: "flex", alignItems: "flex-start", gap: 7, fontSize: 11.5,
                  marginBottom: 5, opacity: ok ? 1 : 0.42
                }}>
                <input type="checkbox" checked={measures.includes(ms.id)} disabled={!ok}
                  onChange={() => toggleMeasure(ms.id)} style={{ marginTop: 2 }} />
                <span style={{ flex: 1 }}>
                  {ms.label}
                  <span className="muted" style={{ fontSize: 10 }}>
                    {" "}— −{ms.effect}% {ms.reduces.replace(/_/g, " ")}
                    {!ok && " · not applicable to this hazard"}
                  </span>
                </span>
              </label>
            );
          })}

          <button className="btn primary wide" style={{ marginTop: 8 }} disabled={busy} onClick={runSim}>
            {busy ? "SIMULATING…" : "RUN SIMULATION"}
          </button>

          {sim && (
            <>
              <SectionTitle>Impact — baseline vs measures</SectionTitle>
              <div className="row" style={{ fontSize: 10, color: "var(--txt-dim)", padding: "2px 0" }}>
                <span style={{ flex: 1 }} />
                <span style={{ width: 74, textAlign: "right" }}>NO MEASURES</span>
                <span style={{ width: 18 }} />
                <span style={{ width: 74, textAlign: "right" }}>WITH</span>
                <span style={{ width: 56, textAlign: "right" }}>CHANGE</span>
              </div>
              <DeltaRow label="People at risk" a={m(sim.baseline, "population_at_risk")} b={m(sim.mitigated, "population_at_risk")} />
              <DeltaRow label="Buildings (severe)" a={m(sim.baseline, "buildings_severe")} b={m(sim.mitigated, "buildings_severe")} />
              <DeltaRow label="Buildings affected" a={m(sim.baseline, "buildings_affected")} b={m(sim.mitigated, "buildings_affected")} />
              <DeltaRow label="Facilities offline" a={m(sim.baseline, "facilities_offline")} b={m(sim.mitigated, "facilities_offline")} />
              <DeltaRow label="Roads blocked" a={m(sim.baseline, "roads_blocked")} b={m(sim.mitigated, "roads_blocked")} />
              <DeltaRow label="Hazard radius" a={m(sim.baseline, "hazard_radius_m")} b={m(sim.mitigated, "hazard_radius_m")} unit=" m" />

              {sim.response && !sim.response.error && (
                <>
                  <SectionTitle>Emergency response under these conditions</SectionTitle>
                  {[
                    ["Normal day", sim.response.normal],
                    ["During event", sim.response.during_event],
                    ["Event + measures", sim.response.with_measures]
                  ].map(([label, r]: any) => (
                    <div key={label} className="row" style={{ fontSize: 11.5, padding: "3px 0" }}>
                      <span style={{ flex: 1 }}>{label}</span>
                      {r ? (
                        <>
                          <span className="mono" style={{ fontSize: 10.5, color: "var(--txt-dim)", marginRight: 8 }}>
                            {r.station_name}
                            {r.staging_distance_m > 0 && (
                              <span style={{ color: "var(--warn)" }}>
                                {" "}· staged {Math.round(r.staging_distance_m)} m out
                              </span>
                            )}
                          </span>
                          <span className="mono" style={{ color: r.within_target ? "var(--good)" : "var(--bad)" }}>
                            {fmtMin(r.response_time_min)}
                          </span>
                        </>
                      ) : (
                        <span className="mono" style={{ color: "var(--bad)" }}>CUT OFF</span>
                      )}
                    </div>
                  ))}
                  <div className="muted" style={{ fontSize: 10.5, marginTop: 4 }}>
                    Roads blocked: {sim.response.roads_blocked_baseline} → {sim.response.roads_blocked_mitigated}
                  </div>
                  {(sim.response.during_event?.staging_distance_m > 0 ||
                    sim.response.with_measures?.staging_distance_m > 0) && (
                    <div className="muted" style={{ fontSize: 10, marginTop: 3, color: "var(--warn)" }}>
                      Where roads at the incident are impassable, the time shown is to the
                      staging point, not the incident — it can look shorter than a normal
                      day while access is actually worse.
                    </div>
                  )}
                </>
              )}

              {(sim.mitigated?.warnings ?? []).concat(sim.comparison?.warnings ?? []).length > 0 && (
                <div style={{ marginTop: 8, fontSize: 10.5, color: "var(--warn)" }}>
                  {(sim.mitigated?.warnings ?? []).concat(sim.comparison?.warnings ?? []).map((w: string, i: number) => (
                    <div key={i}>• {w}</div>
                  ))}
                </div>
              )}
            </>
          )}
        </>
      )}

      {err && (
        <div style={{ marginTop: 10, fontSize: 11, color: "var(--warn)" }}>{err}</div>
      )}

      <button className="btn ghost wide" style={{ marginTop: 10 }}
        onClick={() => { mapBridge.clearEmergency(); setRoutes(null); setSim(null); setErr(null); }}>
        CLEAR MAP
      </button>
    </div>
  );
}
