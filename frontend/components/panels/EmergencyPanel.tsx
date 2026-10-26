"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api/client";
import { mapBridge } from "@/cesium/map-bridge";
import { STUDY_AREAS, compareRoutesOnGraph, haversineDistanceM } from "@/lib/routing-engine";
import { useMapStore } from "@/stores/map-store";
import { useRouteAnalysisStore } from "@/stores/route-analysis-store";
import { useScenarioStore } from "@/stores/scenario-store";
import { useWorkflowStore } from "@/stores/workflow-store";
import { Field, SectionTitle } from "@/components/ui/Bits";
import NextAction from "@/components/workflow/NextAction";
import WorkflowErrorState from "@/components/workflow/WorkflowErrorState";

type Hazard = { id: string; label: string; defaultRadiusM: number; responderType: string };
type Measure = {
  id: string; label: string; reduces: string; effect: number;
  appliesTo: string[]; note: string;
};

const FALLBACK_CATALOGUE: { hazards: Hazard[]; measures: Measure[] } = {
  hazards: [
    { id: "flood", label: "Urban Flood", defaultRadiusM: 450, responderType: "fire_station" },
    { id: "fire", label: "Major Structural Fire", defaultRadiusM: 250, responderType: "fire_station" },
    { id: "chemical", label: "Industrial Hazmat Release", defaultRadiusM: 600, responderType: "hospital" },
    { id: "cyclone", label: "Cyclone / Severe Storm", defaultRadiusM: 800, responderType: "fire_station" },
  ],
  measures: [
    { id: "stormwater_drainage", label: "Stormwater Drainage Upgrade", reduces: "hazard_radius", effect: 25, appliesTo: ["flood", "cyclone"], note: "Reduces flood inundation extent" },
    { id: "firebreaks_hydrants", label: "Hydrant Network Expansion", reduces: "severity", effect: 30, appliesTo: ["fire"], note: "Lowers severe structural exposure" },
    { id: "road_redundancy", label: "Emergency Corridor Hardening", reduces: "road_closures", effect: 40, appliesTo: [], note: "Keeps priority corridors passable" },
  ],
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
  const [err, setErr] = useState<Error | string | null>(null);

  // Incident location. Defaults to the city centre; "pick on map" or typing updates it.
  const [lon, setLon] = useState(73.135);
  const [lat, setLat] = useState(19.002);
  const [lonText, setLonText] = useState("73.135");
  const [latText, setLatText] = useState("19.002");

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
  const incidentPickActive = useMapStore((s) => s.incidentPickActive);
  const setIncidentPickActive = useMapStore((s) => s.setIncidentPickActive);
  const armedSeqRef = useRef<number>(0);
  const pickArmedRef = useRef<boolean>(false);
  const onMapPickRef = useRef<(lonVal: number, latVal: number) => void>(() => {});

  useEffect(() => {
    api.emergencyCatalogue().then((c) => {
      const resolved = c?.hazards?.length ? c : FALLBACK_CATALOGUE;
      setCat(resolved);
      if (resolved.hazards.length && !resolved.hazards.find((h: Hazard) => h.id === hazardType)) {
        setHazardType(resolved.hazards[0].id);
      }
    });
    // Place initial incident pin on mount; clean up pick mode on unmount
    mapBridge.showHazard({ center: [73.135, 19.002], label: "Incident" });
    const unsubClick = useMapStore.subscribe((state) => {
      const clicked = state.lastClick;
      if (
        pickArmedRef.current &&
        clicked &&
        clicked.seq > armedSeqRef.current &&
        typeof clicked.lon === "number" &&
        typeof clicked.lat === "number"
      ) {
        pickArmedRef.current = false;
        armedSeqRef.current = clicked.seq;
        useMapStore.getState().setIncidentPickActive(false);
        onMapPickRef.current(clicked.lon, clicked.lat);
      }
    });
    const onKeyDown = (ev: KeyboardEvent) => {
      if (ev.key === "Escape" && pickArmedRef.current) {
        pickArmedRef.current = false;
        useMapStore.getState().setIncidentPickActive(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      pickArmedRef.current = false;
      unsubClick();
      window.removeEventListener("keydown", onKeyDown);
      useMapStore.getState().setIncidentPickActive(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toBridgeRoute = (r: any, fallbackLon: number, fallbackLat: number) => ({
    stationId: r.station_id,
    stationName: r.station_name,
    path: r.path,
    responseTimeMin: r.response_time_min,
    distanceM: r.distance_m,
    rank: r.rank,
    stationLocation: r.station_location,
    incidentLocation: r.incident_location ?? [fallbackLon, fallbackLat],
    isPrimary: r.is_primary,
    withinTarget: r.within_target,
  });

  const commitTypedCoords = (opts?: { flyTo?: boolean }): { lon: number; lat: number } | null => {
    const parsedLon = Number(lonText);
    const parsedLat = Number(latText);
    if (
      !Number.isFinite(parsedLon) ||
      !Number.isFinite(parsedLat) ||
      Math.abs(parsedLon) > 180 ||
      Math.abs(parsedLat) > 90
    ) {
      setErr("Enter valid incident coordinates (Longitude -180..180, Latitude -90..90).");
      return null;
    }
    const changed =
      Math.abs(parsedLon - lon) > 1e-7 || Math.abs(parsedLat - lat) > 1e-7;
    const cleanLon = Number(parsedLon.toFixed(6));
    const cleanLat = Number(parsedLat.toFixed(6));
    setLon(cleanLon);
    setLat(cleanLat);
    setLonText(String(cleanLon));
    setLatText(String(cleanLat));
    if (changed) {
      setRoutes(null);
      mapBridge.showEmergencyRoutes([]);
    }
    mapBridge.showHazard({
      center: [cleanLon, cleanLat],
      label: "Incident",
      flyTo: opts?.flyTo,
    });
    return { lon: cleanLon, lat: cleanLat };
  };

  const togglePickOnMap = () => {
    if (incidentPickActive || pickArmedRef.current) {
      pickArmedRef.current = false;
      setIncidentPickActive(false);
      return;
    }
    // Record current click sequence so stale clicks never immediately cancel picking
    armedSeqRef.current = useMapStore.getState().clickSeq;
    pickArmedRef.current = true;
    // Clear any competing interaction mode from the guided route panel
    useRouteAnalysisStore.getState().setInteractionMode("navigate");
    setIncidentPickActive(true);
  };

  const hazardSpec = cat.hazards.find((h) => h.id === hazardType);
  const applicable = (m: Measure) => !m.appliesTo.length || m.appliesTo.includes(hazardType);

  const toggleMeasure = (id: string) =>
    setMeasures((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  const ensureStressSession = async (forceNew = false): Promise<string> => {
    const workflowStore = useWorkflowStore.getState();
    if (
      !forceNew &&
      workflowStore.activeWorkflowId === "stress" &&
      workflowStore.context.backendSessionId
    ) {
      return workflowStore.context.backendSessionId;
    }
    const startRes = await api.startWorkflow("stress", activeScenario?.id);
    workflowStore.syncFromBackend(startRes);
    return startRes.session_id;
  };

  const computeOfflineDemoResponderRoutes = (targetLon: number, targetLat: number, responderKind: string) => {
    const raState = useRouteAnalysisStore.getState();
    const areaDef = STUDY_AREAS[raState.studyAreaId];
    const ds = raState.datasets[raState.studyAreaId];
    const builtGraph = raState.graphs[raState.studyAreaId];
    if (!ds || !builtGraph || !areaDef) {
      throw new Error("Study-area road network is still loading. Try again in a moment.");
    }
    const candidates = ds.landmarks
      .filter((lm) =>
        responderKind === "hospital"
          ? lm.category === "hospital" || lm.category === "clinic"
          : responderKind === "fire_station"
          ? lm.category === "fire_station" || lm.category === "emergency" || lm.name.toLowerCase().includes("fire")
          : lm.category === responderKind
      )
      .sort(
        (a, b) =>
          haversineDistanceM([a.lon, a.lat], [targetLon, targetLat]) -
          haversineDistanceM([b.lon, b.lat], [targetLon, targetLat])
      );

    if (!candidates.length) {
      return {
        records: [],
        warnings: [
          `Demo dataset '${areaDef.name}' has no mapped '${responderKind}' facility — switch service to Hospital / ambulance or Fire station.`,
        ],
      };
    }

    const scored: any[] = [];
    for (const fac of candidates.slice(0, 15)) {
      const cmp = compareRoutesOnGraph({
        graph: builtGraph,
        studyArea: areaDef,
        origin: { lon: fac.lon, lat: fac.lat, label: fac.name, source: "landmark" },
        destination: { lon: targetLon, lat: targetLat, label: "Incident", source: "coordinates" },
        scenario: {
          ...raState.draftScenario,
          active: false,
        },
        costMetric: "time",
        dataMode: "demo",
      });
      if (cmp.baselineRoute.feasible && cmp.baselineRoute.travelTimeS !== null) {
        const accessDist =
          (cmp.baselineRoute.snapOriginM ?? 0) + (cmp.baselineRoute.snapDestinationM ?? 0);
        const totalSec = cmp.baselineRoute.travelTimeS + accessDist / 4.2 + turnout;
        const respMin = totalSec / 60;
        scored.push({
          station_id: fac.id,
          station_name: `${fac.name} (Demo OSM)`,
          station_location: [fac.lon, fac.lat],
          incident_location: [targetLon, targetLat],
          distance_m: (cmp.baselineRoute.distanceM ?? 0) + accessDist,
          response_time_min: respMin,
          within_target: respMin <= targetMin,
          path: cmp.baselineRoute.path,
          incident_snap_distance_m: cmp.baselineRoute.snapDestinationM,
        });
      }
    }
    scored.sort((a, b) => a.response_time_min - b.response_time_min);
    const top = scored.slice(0, 3).map((r, idx) => ({
      ...r,
      rank: idx + 1,
      is_primary: idx === 0,
    }));
    return {
      records: top,
      warnings: ["Computed offline over bundled OpenStreetMap graph (Demo Mode)."],
    };
  };

  const isBackendUnreachableError = (errObj: any): boolean => {
    const msg = String(errObj?.message || errObj || "");
    return (
      msg.includes("unreachable") ||
      msg.includes("Failed to fetch") ||
      msg.includes("NetworkError") ||
      msg.includes("HTTP 502") ||
      msg.includes("HTTP 503") ||
      msg.includes("HTTP 504") ||
      msg.includes("AbortError")
    );
  };

  const runRoute = async (
    useHazard = false,
    overrideLon?: number,
    overrideLat?: number,
    overrideResponder?: string
  ) => {
    let targetLon = overrideLon;
    let targetLat = overrideLat;
    if (targetLon === undefined || targetLat === undefined) {
      const parsedLon = Number(lonText);
      const parsedLat = Number(latText);
      if (
        !Number.isFinite(parsedLon) ||
        !Number.isFinite(parsedLat) ||
        Math.abs(parsedLon) > 180 ||
        Math.abs(parsedLat) > 90
      ) {
        setErr("Enter valid incident coordinates (Longitude -180..180, Latitude -90..90).");
        return;
      }
      targetLon = Number(parsedLon.toFixed(6));
      targetLat = Number(parsedLat.toFixed(6));
      setLon(targetLon);
      setLat(targetLat);
    }
    const respType = overrideResponder ?? responder;

    setBusy(true); setErr(null);
    if (!useHazard) setSim(null);
    try {
      let out: any = null;
      const workflowStore = useWorkflowStore.getState();

      try {
        if (
          useHazard &&
          workflowStore.activeWorkflowId === "stress" &&
          workflowStore.context.backendSessionId &&
          workflowStore.completedStepIds.includes("simulate")
        ) {
          try {
            const routeWfRes = await api.stressReroute({
              session_id: workflowStore.context.backendSessionId,
              responder_type: respType,
              target_min: targetMin,
              lon: targetLon,
              lat: targetLat,
              turnout_seconds: turnout,
            });
            workflowStore.syncFromBackend(routeWfRes);
            out = routeWfRes.data || {};
          } catch {
            out = await api.emergencyRoute({
              lon: targetLon,
              lat: targetLat,
              responderType: respType,
              topN: 3,
              turnoutSeconds: turnout,
              responseTargetSeconds: targetMin * 60,
              blockedRoadIds: sim?.network?.blocked_ids ?? [],
              slowedRoadIds: sim?.network?.slowed_ids ?? [],
              scenario_id: activeScenario?.id,
            });
          }
        } else {
          // Always query live PostGIS /api/v1/emergency/route first when reachable
          out = await api.emergencyRoute({
            lon: targetLon,
            lat: targetLat,
            responderType: respType,
            topN: 3,
            turnoutSeconds: turnout,
            responseTargetSeconds: targetMin * 60,
            blockedRoadIds: useHazard ? (sim?.network?.blocked_ids ?? []) : [],
            slowedRoadIds: useHazard ? (sim?.network?.slowed_ids ?? []) : [],
            scenario_id: activeScenario?.id,
          });
        }
      } catch (liveErr: any) {
        if (isBackendUnreachableError(liveErr)) {
          out = computeOfflineDemoResponderRoutes(targetLon, targetLat, respType);
        } else {
          throw liveErr;
        }
      }

      const recs = out?.records ?? [];
      setRoutes(recs);
      mapBridge.showHazard({ center: [targetLon, targetLat], label: "Incident" });
      mapBridge.showEmergencyRoutes(
        recs.map((r: any) => toBridgeRoute(r, targetLon!, targetLat!))
      );
      if (!useHazard) mapBridge.showNetworkImpact(null);
    } catch (e: any) {
      const msg = String(e?.message || e || "");
      if (msg.includes("no '") && msg.includes("facilities in the database")) {
        setRoutes([]);
        mapBridge.showEmergencyRoutes([]);
        setErr(null);
      } else {
        setErr(e);
      }
    } finally { setBusy(false); }
  };

  useEffect(() => {
    onMapPickRef.current = (pickedLon: number, pickedLat: number) => {
      const cleanLon = Number(pickedLon.toFixed(6));
      const cleanLat = Number(pickedLat.toFixed(6));
      setLon(cleanLon);
      setLat(cleanLat);
      setLonText(String(cleanLon));
      setLatText(String(cleanLat));
      setErr(null);
      if (tab === "route") {
        mapBridge.showHazard({ center: [cleanLon, cleanLat], label: "Incident" });
        void runRoute(Boolean(sim?.network?.blocked_count), cleanLon, cleanLat);
      } else {
        setRoutes(null);
        mapBridge.showEmergencyRoutes([]);
        mapBridge.showHazard({ center: [cleanLon, cleanLat], label: "Incident" });
      }
    };
  });

  const runSim = async () => {
    const committed = commitTypedCoords();
    if (!committed) return;
    setBusy(true); setErr(null); setRoutes(null);
    try {
      const workflowStore = useWorkflowStore.getState();
      let sessId = await ensureStressSession(false);

      let simWfRes;
      try {
        simWfRes = await api.stressSimulate({
          session_id: sessId,
          hazard_type: hazardType,
          lon: committed.lon,
          lat: committed.lat,
          radius_m: radius === "" ? null : Number(radius),
          intensity,
          measures
        });
      } catch (innerErr: any) {
        if (isBackendUnreachableError(innerErr)) {
          throw new Error(
            "Full building/population exposure simulation requires Live PostGIS mode. Ensure FastAPI + PostGIS are running, or use the Guided Route Workflow panel on the left for offline Demo Mode route comparison."
          );
        }
        const code = innerErr?.code || "";
        const msg = String(innerErr?.message || "");
        if (
          code === "SESSION_NOT_FOUND" ||
          code === "WORKFLOW_MISMATCH" ||
          msg.includes("Session") ||
          msg.includes("workflow")
        ) {
          sessId = await ensureStressSession(true);
          simWfRes = await api.stressSimulate({
            session_id: sessId,
            hazard_type: hazardType,
            lon: committed.lon,
            lat: committed.lat,
            radius_m: radius === "" ? null : Number(radius),
            intensity,
            measures
          });
        } else {
          throw innerErr;
        }
      }

      workflowStore.syncFromBackend(simWfRes);

      const out = simWfRes.data;
      if (!out) { setErr("No simulation data returned from backend."); return; }
      setSim(out);
      if (out.response?.error) setErr(out.response.error);
      else if (out.persist_error) setErr(`Result not saved: ${out.persist_error}`);
      mapBridge.showHazard({
        center: out.hazard.center, label: out.hazard.label,
        footprint: out.hazard.footprint,
        footprintMitigated: measures.length ? out.hazard.footprint_mitigated : null
      });
      const resp = out.response;
      const draw = resp?.with_measures ?? resp?.during_event ?? resp?.normal;
      if (draw?.path) {
        mapBridge.showEmergencyRoutes([toBridgeRoute(draw, committed.lon, committed.lat)]);
      } else {
        mapBridge.showEmergencyRoutes([]);
      }
      mapBridge.showNetworkImpact(out.network ?? null);
    } catch (e: any) {
      setErr(e);
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
          <input
            className="input"
            type="text"
            inputMode="decimal"
            value={lonText}
            onChange={(e) => setLonText(e.target.value)}
            onBlur={() => commitTypedCoords()}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                const c = commitTypedCoords({ flyTo: true });
                if (c && tab === "route") void runRoute(false, c.lon, c.lat);
              }
            }}
          />
        </Field>
        <Field label="Latitude">
          <input
            className="input"
            type="text"
            inputMode="decimal"
            value={latText}
            onChange={(e) => setLatText(e.target.value)}
            onBlur={() => commitTypedCoords()}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                const c = commitTypedCoords({ flyTo: true });
                if (c && tab === "route") void runRoute(false, c.lon, c.lat);
              }
            }}
          />
        </Field>
      </div>
      <div style={{ display: "flex", gap: 6, alignItems: "center", marginTop: -2, marginBottom: 10 }}>
        <button
          className={incidentPickActive ? "btn primary" : "btn ghost"}
          style={{ fontSize: 10.5, padding: "3px 8px" }}
          onClick={togglePickOnMap}
        >
          {incidentPickActive ? "CLICK ON GLOBE… (ESC/CANCEL)" : "PICK ON MAP"}
        </button>
        <button
          className="btn ghost"
          style={{ fontSize: 10.5, padding: "3px 8px" }}
          onClick={() => commitTypedCoords({ flyTo: true })}
        >
          SHOW
        </button>
        <span className="muted" style={{ fontSize: 10 }}>
          {incidentPickActive ? "click anywhere on 3D map to place & route" : "or type & press Enter"}
        </span>
      </div>

      {tab === "route" ? (
        <>
          <div style={{ display: "flex", gap: 8 }}>
            <Field label="Responding service">
              <select
                className="input"
                value={responder}
                onChange={(e) => {
                  const nextResp = e.target.value;
                  setResponder(nextResp);
                  if (routes !== null) {
                    void runRoute(Boolean(sim?.network?.blocked_count), lon, lat, nextResp);
                  }
                }}
              >
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

          <button className="btn primary wide" disabled={busy} onClick={() => runRoute(false)}>
            {busy ? "ROUTING…" : "FIND FASTEST UNITS"}
          </button>
          {sim?.network?.blocked_count > 0 && (
            <button className="btn ghost wide" style={{ marginTop: 6 }} disabled={busy}
              title="Re-run using the roads closed by the last simulation"
              onClick={() => runRoute(true)}>
              ROUTE THROUGH LAST HAZARD ({sim.network.blocked_count} roads closed)
            </button>
          )}

          {routes && (
            <>
              <SectionTitle>Dispatch order</SectionTitle>
              {routes.length === 0 && (
                <div style={{ fontSize: 11, background: "rgba(239,68,68,.08)",
                              border: "1px solid rgba(239,68,68,.3)",
                              borderRadius: 4, padding: "7px 8px" }}>
                  <b>No unit could reach this incident.</b>
                  <div className="muted" style={{ marginTop: 4, lineHeight: 1.5 }}>
                    Usually one of:
                    <br />• no <span className="mono">{responder}</span> exists in the
                    OpenStreetMap extract — try <b>Hospital / ambulance</b> or <b>Fire station</b>
                    <br />• the incident is far from any mapped road — move it nearer a street
                    <br />• the road network has a gap at this location
                  </div>
                </div>
              )}
              {routes.map((r: any) => (
                <div key={r.station_id} title="Show only this unit's route on the map"
                  onClick={() => {
                    mapBridge.showEmergencyRoutes([
                      { ...toBridgeRoute(r, lon, lat), isPrimary: true }
                    ]);
                  }}
                  style={{
                    display: "flex", alignItems: "center", gap: 8, padding: "5px 7px",
                    marginBottom: 4, borderRadius: 4, cursor: "pointer",
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
              {routes.length > 0 && (
                <div className="row" style={{ fontSize: 10.5, marginTop: 6, gap: 8 }}>
                  <span style={{ flex: 1 }}>
                    <b className="mono" style={{
                      color: routes.some((r: any) => r.within_target) ? "var(--good)" : "var(--bad)"
                    }}>
                      {routes.filter((r: any) => r.within_target).length}/{routes.length}
                    </b>{" "}
                    within the {targetMin} min target
                  </span>
                  <button className="btn ghost" style={{ fontSize: 10, padding: "2px 7px" }}
                    onClick={() => mapBridge.showEmergencyRoutes(routes.map((r: any) => toBridgeRoute(r, lon, lat)))}>
                    SHOW ALL
                  </button>
                </div>
              )}
              <div className="muted" style={{ fontSize: 10.5, marginTop: 4 }}>
                Includes {turnout}s turnout. Target {targetMin} min.
                {routes[0]?.incident_snap_distance_m > 0 &&
                  ` Incident snapped ${Math.round(routes[0].incident_snap_distance_m)} m to the nearest road.`}
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

              {sim.response?.error && (
                <div style={{ marginTop: 8, fontSize: 10.5, color: "var(--warn)",
                              border: "1px solid var(--line)", borderRadius: 4, padding: "6px 7px" }}>
                  Exposure figures above are valid. Response routing could not be
                  computed: {sim.response.error}
                </div>
              )}

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
                        <span className="mono" style={{ color: "var(--bad)" }}
                          title="No station could reach the incident under this condition">
                          CUT OFF
                        </span>
                      )}
                    </div>
                  ))}
                  <div className="muted" style={{ fontSize: 10.5, marginTop: 4 }}>
                    Roads blocked: {sim.response.roads_blocked_baseline} → {sim.response.roads_blocked_mitigated}
                    {sim.network?.reopened_count > 0 &&
                      ` · ${sim.network.reopened_count} reopened by measures (green on map)`}
                    {sim.response.stations_evaluated != null &&
                      ` · ${sim.response.stations_evaluated} station(s) evaluated`}
                  </div>
                  {(sim.response.warnings ?? []).length > 0 && (
                    <div style={{ fontSize: 10, marginTop: 3, color: "var(--warn)" }}>
                      {sim.response.warnings.map((w: string, i: number) => <div key={i}>• {w}</div>)}
                    </div>
                  )}
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

              <NextAction
                title="RESILIENCE DECISION"
                prompt="Disaster simulation complete. Save applied mitigation measures to your scenario or compare with baseline."
                actionLabel="Save Mitigations to Scenario"
                onAction={async () => {
                  const workflowStore = useWorkflowStore.getState();
                  try {
                    const sessId = await ensureStressSession(false);
                    const mitRes = await api.stressMitigate({
                      session_id: sessId,
                      measures
                    });
                    workflowStore.syncFromBackend(mitRes);
                  } catch (e) {
                    console.warn("Workflow mitigate sync skipped:", e);
                  }

                  if (measures.length > 0) {
                    const scStore = useScenarioStore.getState();
                    for (const mId of measures) {
                      const mSpec = cat.measures.find((x) => x.id === mId);
                      await scStore.addChange({
                        type: "facility",
                        label: `Mitigation: ${mSpec?.label || mId}`,
                        detail: `Applies to ${hazardType} · reduces impact by ${mSpec?.effect || 0}%`
                      });
                    }
                  }
                }}
                targetWindow="changes"
                secondaryActionLabel="Compare Scenarios"
                secondaryTargetWindow="comparison"
                variant="good"
              />
            </>
          )}
        </>
      )}

      {(routes || sim) && (
        <div style={{ marginTop: 10, fontSize: 10, opacity: 0.75,
                      display: "flex", flexWrap: "wrap", gap: 10 }}>
          <Key c="#00e5ff" t="fastest unit" />
          <Key c="#7d8ea0" t="other units" />
          {sim && <Key c="#ef4444" t="road closed" />}
          {sim && <Key c="#fbbf24" t="road slowed" />}
          {sim && <Key c="#22c55e" t="reopened by measure" />}
        </div>
      )}

      {err && (
        <WorkflowErrorState
          error={err}
          step={tab}
          onRetry={() => (tab === "route" ? runRoute(false) : runSim())}
          onBack={() => setErr(null)}
        />
      )}

      <button className="btn ghost wide" style={{ marginTop: 10 }}
        onClick={() => { mapBridge.clearEmergency(); setRoutes(null); setSim(null); setErr(null); }}>
        CLEAR MAP
      </button>
    </div>
  );
}

/** Map colour key. */
function Key({ c, t }: { c: string; t: string }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
      <span style={{ width: 14, height: 3, background: c, borderRadius: 2 }} />
      {t}
    </span>
  );
}