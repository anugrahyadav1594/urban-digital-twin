"use client";
import { useEffect, useRef, useState } from "react";
import { CITY_CENTER, ION_TOKEN } from "@/lib/constants";
import { FACILITIES, FLOOD_ZONE, PARCELS, ROADS, ZONE_COLOR } from "@/lib/city-model";
import { mapBridge } from "./map-bridge";
import { useLayerStore } from "@/stores/layer-store";
import { useMapStore } from "@/stores/map-store";
import { useSelectionStore } from "@/stores/selection-store";
import { useWindowStore } from "@/stores/window-store";
import type { LayerKind, ResultEntity } from "@/types";

/** CesiumJS is loaded from /public/cesium by a <script> in app/layout.tsx. */
async function waitForCesium(): Promise<any> {
  for (let i = 0; i < 200; i++) {
    const C = (window as any).Cesium;
    if (C) return C;
    await new Promise((r) => setTimeout(r, 50));
  }
  throw new Error("CesiumJS did not load from /cesium/Cesium.js - run `npm install` so the assets are copied into public/cesium.");
}

const ChevronUpIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="m18 15-6-6-6 6"/></svg>
);

const ChevronDownIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="m6 9 6 6 6-6"/></svg>
);

const ChevronLeftIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6"/></svg>
);

const ChevronRightIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="m9 18 6-6-6-6"/></svg>
);

const PlusIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14"/><path d="M12 5v14"/></svg>
);

const MinusIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14"/></svg>
);

const RefreshCwIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/></svg>
);

const RotateCcwIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
);

const RotateCwIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12a9 9 0 1 1-9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/></svg>
);

const CompassIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/></svg>
);

const HomeIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
);

function createProceduralStarfieldSkyBox(Cesium: any) {
  const size = 512;
  const faces: Record<string, string> = {};
  const faceNames = ["positiveX", "negativeX", "positiveY", "negativeY", "positiveZ", "negativeZ"];

  faceNames.forEach((face, index) => {
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Deep Space Dark Canvas
    ctx.fillStyle = "#02040a";
    ctx.fillRect(0, 0, size, size);

    const seed = (index + 1) * 1337;
    const pseudoRng = (n: number) => {
      const x = Math.sin(seed + n * 91.34) * 43758.5453;
      return x - Math.floor(x);
    };

    // Soft Galaxy Nebulae Dust (Purple / Indigo / Cyan cosmic dust)
    for (let i = 0; i < 2; i++) {
      const gx = pseudoRng(i * 10) * size;
      const gy = pseudoRng(i * 20) * size;
      const gr = 100 + pseudoRng(i * 30) * 160;

      const grad = ctx.createRadialGradient(gx, gy, 0, gx, gy, gr);
      const col = i % 2 === 0 ? "rgba(99, 102, 241, 0.14)" : "rgba(168, 85, 247, 0.10)";
      grad.addColorStop(0, col);
      grad.addColorStop(0.5, "rgba(56, 189, 248, 0.04)");
      grad.addColorStop(1, "rgba(2, 4, 10, 0)");

      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(gx, gy, gr, 0, Math.PI * 2);
      ctx.fill();
    }

    // High-Quality Pin-Point Stars with Natural Color Tints
    const starCount = 160;
    for (let i = 0; i < starCount; i++) {
      const sx = pseudoRng(i * 3 + 1) * size;
      const sy = pseudoRng(i * 3 + 2) * size;
      const brightness = 0.35 + pseudoRng(i * 3 + 3) * 0.65;
      const radius = pseudoRng(i * 7) > 0.94 ? 1.4 : pseudoRng(i * 7) > 0.75 ? 1.0 : 0.6;

      const tint = pseudoRng(i * 11);
      const starColor = tint > 0.82 ? `rgba(186, 230, 253, ${brightness})`
        : tint > 0.68 ? `rgba(254, 240, 138, ${brightness})`
        : `rgba(255, 255, 255, ${brightness})`;

      ctx.fillStyle = starColor;
      ctx.beginPath();
      ctx.arc(sx, sy, radius, 0, Math.PI * 2);
      ctx.fill();

      if (radius > 1.2) {
        ctx.fillStyle = `rgba(255, 255, 255, ${brightness * 0.3})`;
        ctx.beginPath();
        ctx.arc(sx, sy, radius * 2.2, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    faces[face] = canvas.toDataURL("image/png");
  });

  return new Cesium.SkyBox({ sources: faces });
}

export default function CesiumViewer() {
  const hostRef = useRef<HTMLDivElement>(null);
  const bootedRef = useRef(false);
  const [autoSpin, setAutoSpin] = useState(false);
  const autoSpinRef = useRef(false);
  const [viewMode, setViewMode] = useState<"perspective" | "topDown">("perspective");
  const activeViewModeRef = useRef<"perspective" | "topDown">("perspective");
  const [isOrbitView, setIsOrbitView] = useState(false);
  const isOrbitViewRef = useRef(false);
  const { setReady, setError, setCameraText } = useMapStore();
  const select = useSelectionStore((s) => s.select);
  const openWindow = useWindowStore((s) => s.openWindow);
  const layers = useLayerStore((s) => s.layers);
  const year = useMapStore((s) => s.year);
  const drawMode = useMapStore((s) => s.drawMode);
  const setDrawnPath = useMapStore((s) => s.setDrawnPath);

  useEffect(() => {
    if (bootedRef.current || !hostRef.current) return;
    bootedRef.current = true;
    let viewer: any;
    let disposed = false;
    let removeTick: (() => void) | undefined;

    (async () => {
      try {
        const Cesium: any = await waitForCesium();
        if (disposed || !hostRef.current) return;

        if (ION_TOKEN) Cesium.Ion.defaultAccessToken = ION_TOKEN;

        viewer = new Cesium.Viewer(hostRef.current, {
          baseLayer: ION_TOKEN
            ? undefined
            : Cesium.ImageryLayer.fromProviderAsync(
              Promise.resolve(new Cesium.UrlTemplateImageryProvider({
                url: "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
                credit: "© OpenStreetMap contributors, © CARTO",
                maximumLevel: 20
              })),
              {}
            ),
          animation: false, timeline: false, geocoder: false, homeButton: false,
          sceneModePicker: false, baseLayerPicker: false, navigationHelpButton: false,
          fullscreenButton: false, infoBox: false, selectionIndicator: false,
          creditContainer: document.createElement("div"),
          requestRenderMode: false
        });

        const mainBaseLayer = viewer.imageryLayers.get(0);
        if (mainBaseLayer) {
          mainBaseLayer.brightness = 1.0;
          mainBaseLayer.contrast = 1.0;
          mainBaseLayer.saturation = 1.0;
        }

        // Authoritative International & State Boundaries and Place Names Reference Layer
        viewer.imageryLayers.addImageryProvider(
          new Cesium.UrlTemplateImageryProvider({
            url: "https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
            credit: "Esri, HERE, © OpenStreetMap contributors",
            maximumLevel: 16
          })
        );

        // Authoritative Geographic Waterbodies & Hydrography Reference Layer (Oceans, Seas, Rivers, Lakes & Reservoirs everywhere)
        const waterImageryProvider = new Cesium.UrlTemplateImageryProvider({
          url: "https://services.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Reference/MapServer/tile/{z}/{y}/{x}",
          credit: "Esri, GEBCO, NOAA, CHS",
          maximumLevel: 16
        });
        const waterImageryLayer = viewer.imageryLayers.addImageryProvider(waterImageryProvider);

        // Load Indian Inter-State Boundaries ONLY (visible from country-wide zoom extent down to city level)
        Cesium.GeoJsonDataSource.load("/data/india-states.json", {
          stroke: Cesium.Color.fromCssColorString("#cbd5e1").withAlpha(0.85),
          strokeWidth: 2.0,
          fill: Cesium.Color.TRANSPARENT,
          clampToGround: true
        }).then((indiaStateDs: any) => {
          if (!disposed && viewer) {
            indiaStateDs.entities.values.forEach((e: any) => {
              // Strip 2D polygon fill to eliminate black square artifacts when zooming
              e.polygon = undefined;

              if (e.polyline) {
                e.polyline.width = 2.0;
                e.polyline.material = Cesium.Color.fromCssColorString("#cbd5e1").withAlpha(0.85);
                // Infinite visibility distance (visible from planetary orbit down to ground level)
                e.polyline.distanceDisplayCondition = undefined;
                e.polyline.clampToGround = true;
              }
            });
            viewer.dataSources.add(indiaStateDs);
          }
        }).catch((err: any) => console.warn("[cesium] india-states load error", err));

        // Native display resolution scaling for crisp, non-blurry rendering
        viewer.resolutionScale = Math.min(2.0, window.devicePixelRatio || 1.0);

        // High Dynamic Range & Post-Processing Anti-Aliasing
        viewer.scene.highDynamicRange = true;
        if (viewer.scene.postProcessStages?.fxaa) {
          viewer.scene.postProcessStages.fxaa.enabled = true;
        }

        // Hide Sun & Moon celestial entities
        if (viewer.scene.sun) viewer.scene.sun.show = false;
        if (viewer.scene.moon) viewer.scene.moon.show = false;

        // Screen-Anchored Light Vector: Light shines from lower-right (+right, -up) to position limb shadow on upper-left
        const getScreenAnchoredLightDirection = () => {
          const camera = viewer.camera;
          const forward = camera.directionWC;
          const right = camera.rightWC;
          const up = camera.upWC;

          const dir = new Cesium.Cartesian3();
          Cesium.Cartesian3.add(forward, Cesium.Cartesian3.multiplyByScalar(right, 0.55, new Cesium.Cartesian3()), dir);
          Cesium.Cartesian3.add(dir, Cesium.Cartesian3.multiplyByScalar(up, -0.35, new Cesium.Cartesian3()), dir);
          return Cesium.Cartesian3.normalize(dir, dir);
        };

        const cameraLight = new Cesium.DirectionalLight({
          direction: getScreenAnchoredLightDirection()
        });
        viewer.scene.light = cameraLight;

        // 3D Shadows & Google Earth Limb Shadow
        viewer.shadows = true;
        viewer.terrainShadows = Cesium.ShadowMode.ENABLED;
        viewer.scene.globe.enableLighting = true; // Renders the soft Google Earth limb shadow on the sphere edge
        if (viewer.shadowMap) {
          viewer.shadowMap.softShadows = true;
          viewer.shadowMap.darkness = 0.45;
          viewer.shadowMap.size = 2048;
        }

        // Lightweight, High-Quality Procedural Starfield & Galaxy SkyBox (Low-End PC Optimized)
        try {
          viewer.scene.skyBox = createProceduralStarfieldSkyBox(Cesium);
          viewer.scene.skyBox.show = true;
        } catch {
          if (viewer.scene.skyBox) viewer.scene.skyBox.show = false;
        }
        viewer.scene.backgroundColor = Cesium.Color.fromCssColorString("#02040a");
        viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString("#0d1f38");
        viewer.scene.skyAtmosphere.show = true;
        viewer.scene.skyAtmosphere.brightnessShift = 0.15;
        viewer.scene.fog.enabled = true;
        viewer.scene.fog.density = 0.0001;
        const controller = viewer.scene.screenSpaceCameraController;
        controller.enableCollisionDetection = true;
        controller.minimumZoomDistance = 50;
        controller.constrainedAxis = Cesium.Cartesian3.UNIT_Z; // North-up vertical lock
        controller.minimumPitch = Cesium.Math.toRadians(-88);
        controller.maximumPitch = Cesium.Math.toRadians(-2);
        controller.enableLook = false;
        controller.enableRotate = true;
        controller.enableTilt = true;
        controller.enableTranslate = true;
        controller.enableZoom = true;
        controller.translateEventTypes = [Cesium.CameraEventType.LEFT_DRAG];
        controller.tiltEventTypes = [
          Cesium.CameraEventType.MIDDLE_DRAG,
          { eventType: Cesium.CameraEventType.LEFT_DRAG, modifier: Cesium.KeyboardEventModifier.SHIFT },
          { eventType: Cesium.CameraEventType.LEFT_DRAG, modifier: Cesium.KeyboardEventModifier.CTRL },
          { eventType: Cesium.CameraEventType.RIGHT_DRAG, modifier: Cesium.KeyboardEventModifier.CTRL }
        ];
        controller.zoomEventTypes = [
          Cesium.CameraEventType.RIGHT_DRAG,
          Cesium.CameraEventType.WHEEL,
          Cesium.CameraEventType.PINCH
        ];
        controller.inertiaSpin = 0.88;
        controller.inertiaTranslate = 0.88;
        controller.inertiaZoom = 0.82;
        controller.maximumMovementRatio = 0.2;

        /* ── data sources, one per logical layer ─────────────── */
        const ds: Record<string, any> = {};
        const currentLayers = useLayerStore.getState().layers;
        for (const key of ["buildings", "parcels", "roads", "highways", "landuse", "population", "water", "flood", "facilities", "candidates", "proposals"]) {
          ds[key] = new Cesium.CustomDataSource(key);
          const found = currentLayers.find((l) => l.id === key);
          if (found) ds[key].show = found.visible;
          viewer.dataSources.add(ds[key]);
        }

        const C = (hex: string, a = 1) => Cesium.Color.fromCssColorString(hex).withAlpha(a);
        const baseHeights = new Map<string, number>();

        /* buildings */
        for (const p of PARCELS) {
          if (p.floors <= 0) continue;
          const w = 55 + (p.areaM2 % 60);
          baseHeights.set(p.id, p.heightM);
          ds.buildings.entities.add({
            id: p.id,
            position: Cesium.Cartesian3.fromDegrees(p.lon, p.lat, p.heightM / 2),
            box: {
              dimensions: new Cesium.Cartesian3(w, w * 0.8, p.heightM),
              material: C(p.floors > 10 ? "#9fb6d6" : p.floors > 5 ? "#7d93b3" : "#63788f", 0.95),
              outline: true,
              outlineColor: C("#0b1220", 0.8)
            },
            properties: { kind: "parcel" }
          });
        }

        /* parcels (footprints) */
        for (const p of PARCELS) {
          const d = 0.00075;
          ds.parcels.entities.add({
            id: "pf_" + p.id,
            rectangle: {
              coordinates: Cesium.Rectangle.fromDegrees(p.lon - d, p.lat - d, p.lon + d, p.lat + d),
              material: C("#22d3ee", 0.1),
              outline: true, outlineColor: C("#22d3ee", 0.55), height: 1
            },
            properties: { kind: "parcel", ref: p.id }
          });
        }

        /* land use + population choropleths */
        for (const p of PARCELS) {
          const d = 0.0009;
          const rect = Cesium.Rectangle.fromDegrees(p.lon - d, p.lat - d, p.lon + d, p.lat + d);
          ds.landuse.entities.add({
            id: "lu_" + p.id,
            rectangle: { coordinates: rect, material: C(ZONE_COLOR[p.zoning], 0.45), height: 2 },
            properties: { kind: "parcel", ref: p.id }
          });
          const pop = p.population;
          const col = pop > 800 ? "#fb923c" : pop > 500 ? "#e11d48" : pop > 200 ? "#7c3aed" : "#1e3a8a";
          ds.population.entities.add({
            id: "pop_" + p.id,
            rectangle: { coordinates: rect, material: C(col, 0.5), height: 3 },
            properties: { kind: "parcel", ref: p.id }
          });
          if (p.flood !== "Low") {
            ds.flood.entities.add({
              id: "fl_" + p.id,
              rectangle: { coordinates: rect, material: C(p.flood === "High" ? "#ef4444" : "#f59e0b", 0.42), height: 4 },
              properties: { kind: "parcel", ref: p.id }
            });
          }
        }

        /* roads — all roads go into ds.roads */
        for (const r of ROADS) {
          ds.roads.entities.add({
            id: r.id,
            polyline: {
              positions: Cesium.Cartesian3.fromDegreesArray(r.path.flat()),
              width: r.type === "Arterial" ? 6 : 3.5,
              material: C(r.type === "Arterial" ? "#f8fafc" : "#94a3b8", 0.75),
              clampToGround: true
            },
            properties: { kind: "road" }
          });
        }

        /* ── national highways overlay ───────────────────────── */
        // Esri World Transportation tile layer — shows ALL national highways
        // across India with proper NH numbers, road names, and route markings.
        const hwImageryProvider = new Cesium.UrlTemplateImageryProvider({
          url: "https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}",
          credit: "Esri, HERE, © OpenStreetMap contributors",
          maximumLevel: 16
        });
        const hwImageryLayer = viewer.imageryLayers.addImageryProvider(hwImageryProvider);
        const hwStoreVis = currentLayers.find((l) => l.id === "highways")?.visible ?? true;
        hwImageryLayer.show = hwStoreVis;

        // Store reference to imagery layer for toggle
        (ds.highways as any)._imageryLayer = hwImageryLayer;

        // Store reference to waterbodies imagery layer for toggle
        (ds.water as any)._imageryLayer = waterImageryLayer;
        const waterStoreVis = currentLayers.find((l) => l.id === "water")?.visible ?? true;
        waterImageryLayer.show = waterStoreVis;

        /* facilities */
        const glyph: Record<string, string> = { Hospital: "H", School: "S", "Fire Station": "F", Metro: "M" };
        for (const f of FACILITIES) {
          ds.facilities.entities.add({
            id: f.id,
            position: Cesium.Cartesian3.fromDegrees(f.lon, f.lat, 60),
            point: { pixelSize: 12, color: C("#34d399"), outlineColor: C("#04140d"), outlineWidth: 2 },
            label: {
              text: glyph[f.type] + " · " + f.name,
              font: "11px monospace", fillColor: C("#d1fae5"),
              showBackground: true, backgroundColor: C("#04211a", 0.75),
              pixelOffset: new Cesium.Cartesian2(0, -20),
              verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
              distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 14000)
            },
            properties: { kind: "facility" }
          });
        }

        /* ── picking ─────────────────────────────────────────── */
        let highlighted: any[] = [];
        const clearHighlight = () => {
          highlighted.forEach((e) => {
            if (e.box) e.box.material = e.__origMat;
            if (e.rectangle) e.rectangle.material = e.__origMat;
          });
          highlighted = [];
        };
        const applyHighlight = (ids: string[]) => {
          clearHighlight();
          ids.forEach((id) => {
            const e = ds.buildings.entities.getById(id) || ds.parcels.entities.getById("pf_" + id);
            if (!e) return;
            e.__origMat = e.box ? e.box.material : e.rectangle?.material;
            const mat = C("#38bdf8", 0.95);
            if (e.box) e.box.material = mat;
            else if (e.rectangle) e.rectangle.material = mat;
            highlighted.push(e);
          });
        };

        const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
        handler.setInputAction((click: any) => {
          const mode = useMapStore.getState().drawMode;
          const cart = viewer.scene.pickPosition(click.position) ?? viewer.camera.pickEllipsoid(click.position, viewer.scene.globe.ellipsoid);

          if (mode !== "select" && cart) {
            const carto = Cesium.Cartographic.fromCartesian(cart);
            const lon = Cesium.Math.toDegrees(carto.longitude);
            const lat = Cesium.Math.toDegrees(carto.latitude);

            if (mode === "road") {
              const path = [...useMapStore.getState().drawnPath, [lon, lat] as [number, number]];
              setDrawnPath(path);
              ds.proposals.entities.removeById("draft_road");
              if (path.length > 1) {
                ds.proposals.entities.add({
                  id: "draft_road",
                  polyline: { positions: Cesium.Cartesian3.fromDegreesArray(path.flat()), width: 8, material: C("#a855f7", 0.9), clampToGround: true }
                });
              }
              ds.proposals.entities.add({
                id: "draft_pt_" + path.length,
                position: Cesium.Cartesian3.fromDegrees(lon, lat, 5),
                point: { pixelSize: 8, color: C("#a855f7"), outlineColor: C("#fff"), outlineWidth: 1 }
              });
              return;
            }

            const label: Record<string, string> = { hospital: "Proposed hospital", school: "Proposed school", fire: "Proposed fire station", zone: "Proposed zone" };
            if (label[mode]) {
              ds.proposals.entities.add({
                id: "prop_" + Date.now(),
                position: Cesium.Cartesian3.fromDegrees(lon, lat, 40),
                cylinder: { length: 80, topRadius: 0, bottomRadius: 45, material: C("#a855f7", 0.85) },
                label: {
                  text: label[mode], font: "11px monospace", fillColor: C("#f3e8ff"),
                  showBackground: true, backgroundColor: C("#2e1065", 0.8),
                  pixelOffset: new Cesium.Cartesian2(0, -26), verticalOrigin: Cesium.VerticalOrigin.BOTTOM
                }
              });
              return;
            }
          }

          const picked = viewer.scene.pick(click.position);
          const id = picked?.id?.id as string | undefined;
          if (!id) { select(null); clearHighlight(); return; }
          const ref = (id.startsWith("pf_") || id.startsWith("lu_") || id.startsWith("pop_") || id.startsWith("fl_")) ? id.slice(id.indexOf("_") + 1) : id;
          select(ref);
          applyHighlight([ref]);
          openWindow("inspector");
        }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

        /* camera readout & screen-anchored light update & altitude 3D limit check */
        viewer.camera.changed.addEventListener(() => {
          if (cameraLight && viewer.camera) {
            cameraLight.direction = getScreenAnchoredLightDirection();
          }
          if (Math.abs(viewer.camera.roll) > 0.0001) {
            viewer.camera.setView({
              orientation: {
                heading: viewer.camera.heading,
                pitch: viewer.camera.pitch,
                roll: 0.0
              }
            });
          }
          const c = Cesium.Cartographic.fromCartesian(viewer.camera.positionWC);

          // 3D View Altitude Limit (1,000,000 meters / 1,000 km altitude threshold)
          const isTooFar = c.height > 1000000;
          if (isTooFar !== isOrbitViewRef.current) {
            isOrbitViewRef.current = isTooFar;
            setIsOrbitView(isTooFar);

            // Automatically switch 3D perspective to 2D top-down when zoomed out beyond 1,000 km
            if (isTooFar && activeViewModeRef.current === "perspective") {
              activeViewModeRef.current = "topDown";
              setViewMode("topDown");
              viewer.camera.flyTo({
                destination: viewer.camera.positionWC,
                orientation: {
                  heading: viewer.camera.heading,
                  pitch: Cesium.Math.toRadians(-90),
                  roll: 0
                },
                duration: 0.8
              });
            }
          }

          setCameraText(
            Cesium.Math.toDegrees(c.latitude).toFixed(4) + "°N  " +
            Cesium.Math.toDegrees(c.longitude).toFixed(4) + "°E  " +
            (c.height / 1000).toFixed(1) + " km"
          );
        });

        /* Get map location under the screen center */
        const getCenterLocation = () => {
          if (!viewer || !Cesium) return { lon: CITY_CENTER.lon, lat: CITY_CENTER.lat };
          const centerPixel = new Cesium.Cartesian2(
            viewer.canvas.clientWidth / 2,
            viewer.canvas.clientHeight / 2
          );
          const cartesian = viewer.scene.pickPosition(centerPixel) ??
            viewer.camera.pickEllipsoid(centerPixel, viewer.scene.globe.ellipsoid);
          if (cartesian) {
            const carto = Cesium.Cartographic.fromCartesian(cartesian);
            return {
              lon: Cesium.Math.toDegrees(carto.longitude),
              lat: Cesium.Math.toDegrees(carto.latitude)
            };
          }
          const cCart = Cesium.Cartographic.fromCartesian(viewer.camera.positionWC);
          return {
            lon: Cesium.Math.toDegrees(cCart.longitude),
            lat: Cesium.Math.toDegrees(cCart.latitude)
          };
        };

        /* shortest route navigation with customizable orientation */
        const flyHomeShortestRoute = (
          targetLon = CITY_CENTER.lon,
          targetLat = CITY_CENTER.lat - 0.035,
          targetAlt = 3600,
          orientation: { heading?: number; pitch?: number; roll?: number } = {}
        ) => {
          if (!viewer || !Cesium) return;
          const cCart = Cesium.Cartographic.fromCartesian(viewer.camera.positionWC);
          const cLon = Cesium.Math.toDegrees(cCart.longitude);
          const cLat = Cesium.Math.toDegrees(cCart.latitude);
          const cAlt = cCart.height;

          // Shortest longitude delta [-180, 180]
          const dLon = ((targetLon - cLon + 540) % 360) - 180;
          const destinationLon = cLon + dLon;

          // Spherical angular distance calculation
          const rLat1 = Cesium.Math.toRadians(cLat);
          const rLat2 = Cesium.Math.toRadians(targetLat);
          const rDLon = Cesium.Math.toRadians(dLon);

          const cosAngle = Math.sin(rLat1) * Math.sin(rLat2) + Math.cos(rLat1) * Math.cos(rLat2) * Math.cos(rDLon);
          const angDist = Math.acos(Math.max(-1, Math.min(1, cosAngle)));

          const distM = angDist * 6371000;
          const baseMaxAlt = Math.max(cAlt, targetAlt);
          const maxFlightAlt = Math.min(10000, baseMaxAlt + Math.min(5000, distM * 0.12));
          const flightDuration = Math.min(3.2, Math.max(1.2, angDist * 2.0));

          viewer.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(destinationLon, targetLat, targetAlt),
            orientation: {
              heading: orientation.heading ?? 0,
              pitch: orientation.pitch ?? Cesium.Math.toRadians(-38),
              roll: orientation.roll ?? 0
            },
            duration: flightDuration,
            maximumHeight: maxFlightAlt,
            easingFunction: Cesium.EasingFunction.QUADRATIC_IN_OUT
          });
        };

        const home = () => {
          if (activeViewModeRef.current === "topDown") {
            flyHomeShortestRoute(CITY_CENTER.lon, CITY_CENTER.lat, 6500, {
              heading: 0,
              pitch: Cesium.Math.toRadians(-90),
              roll: 0
            });
          } else {
            flyHomeShortestRoute(CITY_CENTER.lon, CITY_CENTER.lat - 0.035, 3600, {
              heading: 0,
              pitch: Cesium.Math.toRadians(-38),
              roll: 0
            });
          }
        };

        const topDown = (location?: { lon: number; lat: number; height?: number }) => {
          if (!viewer || !Cesium) return;
          activeViewModeRef.current = "topDown";
          setViewMode("topDown");
          const loc = location ?? getCenterLocation();
          const cCart = Cesium.Cartographic.fromCartesian(viewer.camera.positionWC);
          const targetAlt = location?.height ?? Math.max(1200, cCart.height);
          flyHomeShortestRoute(loc.lon, loc.lat, targetAlt, {
            heading: 0,
            pitch: Cesium.Math.toRadians(-90),
            roll: 0
          });
        };

        const perspectiveView = (location?: { lon: number; lat: number; height?: number }) => {
          if (!viewer || !Cesium) return;
          activeViewModeRef.current = "perspective";
          setViewMode("perspective");
          const loc = location ?? getCenterLocation();
          const cCart = Cesium.Cartographic.fromCartesian(viewer.camera.positionWC);
          const targetAlt = location?.height ?? Math.max(1500, cCart.height);
          flyHomeShortestRoute(loc.lon, loc.lat - 0.02, targetAlt, {
            heading: 0,
            pitch: Cesium.Math.toRadians(-38),
            roll: 0
          });
        };

        const alignNorth = () => {
          if (!viewer || !Cesium) return;

          // Stop auto-spin if active so camera stays locked to True North and does not rotate on its own
          if (autoSpinRef.current) {
            autoSpinRef.current = false;
            setAutoSpin(false);
          }

          const currentPitch = viewer.camera.pitch;
          const cart = Cesium.Cartographic.fromCartesian(viewer.camera.positionWC);
          const center = getCenterLocation();

          viewer.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(center.lon, center.lat, cart.height),
            orientation: {
              heading: 0,
              pitch: currentPitch,
              roll: 0
            },
            duration: 0.8,
            easingFunction: Cesium.EasingFunction.QUADRATIC_IN_OUT
          });
        };

        const zoomIn = () => {
          if (!viewer || !Cesium) return;
          const cart = Cesium.Cartographic.fromCartesian(viewer.camera.positionWC);
          if (cart.height <= 60) return; // Prevent going below minimum altitude
          const zoomAmount = Math.min(cart.height * 0.35, cart.height - 50);
          if (zoomAmount > 0) viewer.camera.zoomIn(zoomAmount);
        };

        const zoomOut = () => {
          if (!viewer || !Cesium) return;
          const cart = Cesium.Cartographic.fromCartesian(viewer.camera.positionWC);
          viewer.camera.zoomOut(cart.height * 0.45);
        };

        const setOrientation = (mode: "perspective" | "topDown", location?: { lon: number; lat: number; height?: number }) => {
          if (mode === "topDown") topDown(location);
          else perspectiveView(location);
        };

        const toggleViewMode = () => {
          if (isOrbitViewRef.current) return;
          if (activeViewModeRef.current === "perspective") {
            topDown();
          } else {
            perspectiveView();
          }
        };

        const rotateGlobe = (dir: "up" | "down" | "left" | "right" | "rollLeft" | "rollRight") => {
          if (!viewer || !Cesium) return;
          const step = Cesium.Math.toRadians(12);
          switch (dir) {
            case "up": viewer.camera.rotateUp(step); break;
            case "down": viewer.camera.rotateDown(step); break;
            case "left": viewer.camera.rotateLeft(step); break;
            case "right": viewer.camera.rotateRight(step); break;
            case "rollLeft": viewer.camera.twistLeft(step); break;
            case "rollRight": viewer.camera.twistRight(step); break;
          }
        };

        const toggleAutoRotate = () => {
          autoSpinRef.current = !autoSpinRef.current;
          setAutoSpin(autoSpinRef.current);
        };

        const toggleHighways = (show?: boolean) => {
          if (ds.highways) {
            const next = show ?? !ds.highways.show;
            ds.highways.show = next;
            // Also toggle the imagery tile layer
            if ((ds.highways as any)._imageryLayer) {
              (ds.highways as any)._imageryLayer.show = next;
            }
            useLayerStore.getState().setVisible("highways", next);
          }
        };

        removeTick = viewer.clock.onTick.addEventListener(() => {
          if (autoSpinRef.current && viewer) {
            viewer.camera.rotateRight(0.0035);
          }
        });

        /* ── bridge API ──────────────────────────────────────── */
        mapBridge.register({
          home,
          topDown,
          perspectiveView,
          setOrientation,
          toggleViewMode,
          alignNorth,
          zoomIn,
          zoomOut,
          rotateGlobe,
          toggleAutoRotate,
          toggleHighways,
          flyTo: (entityId: string) => {
            const p = PARCELS.find((x) => x.id === entityId);
            const f = FACILITIES.find((x) => x.id === entityId);
            const target = p ?? f;
            if (!target) return;
            flyHomeShortestRoute(target.lon, target.lat - 0.014, 2100);
            applyHighlight([entityId]);
          },
          highlight: applyHighlight,
          setLayerVisible: (id: LayerKind, v: boolean) => {
            if (ds[id]) {
              ds[id].show = v;
              // Also toggle imagery layer for highways & waterbodies
              if (id === "highways" && (ds.highways as any)?._imageryLayer) {
                (ds.highways as any)._imageryLayer.show = v;
              }
              if (id === "water" && (ds.water as any)?._imageryLayer) {
                (ds.water as any)._imageryLayer.show = v;
              }
            }
          },
          setLayerOpacity: (id: LayerKind, o: number) => {
            const src = ds[id];
            if (!src) return;
            src.entities.values.forEach((e: any) => {
              const target = e.rectangle ?? e.polyline ?? e.box;
              const mat = target?.material;
              const col = mat?.color?.getValue?.(Cesium.JulianDate.now());
              if (col) mat.color = col.withAlpha(Math.max(0.05, o));
            });
          },
          showCandidates: (entities: ResultEntity[]) => {
            ds.candidates.entities.removeAll();
            entities.forEach((c, i) => {
              ds.candidates.entities.add({
                id: "cand_" + c.entityId,
                position: Cesium.Cartesian3.fromDegrees(c.position.lon, c.position.lat, 120),
                cylinder: {
                  length: 240, topRadius: 0, bottomRadius: 70 - i * 4,
                  material: C(i === 0 ? "#fde047" : i < 3 ? "#38bdf8" : "#64748b", 0.9)
                },
                label: {
                  text: "#" + (i + 1) + "  " + c.score.toFixed(1),
                  font: "bold 12px monospace", fillColor: C("#0b1220"),
                  showBackground: true, backgroundColor: C(i === 0 ? "#fde047" : "#38bdf8", 0.92),
                  pixelOffset: new Cesium.Cartesian2(0, -40), verticalOrigin: Cesium.VerticalOrigin.BOTTOM
                }
              });
              ds.candidates.entities.add({
                id: "cand_ring_" + c.entityId,
                position: Cesium.Cartesian3.fromDegrees(c.position.lon, c.position.lat, 6),
                ellipse: {
                  semiMajorAxis: 1400, semiMinorAxis: 1400,
                  material: C(i === 0 ? "#fde047" : "#38bdf8", 0.06),
                  outline: true, outlineColor: C(i === 0 ? "#fde047" : "#38bdf8", 0.35), height: 6
                }
              });
            });
            if (entities[0]) mapBridge.flyTo(entities[0].entityId);
          },
          clearCandidates: () => ds.candidates.entities.removeAll(),
          clearProposals: () => ds.proposals.entities.removeAll(),
          setDrawMode: () => { },
          placeFacility: () => { },
          setYear: (y: number) => {
            const growth = 1 + Math.max(0, (y - 2026) / 14) * 0.55;
            ds.buildings.entities.values.forEach((e: any) => {
              const base = baseHeights.get(e.id) ?? 10;
              const h = base * growth;
              const dim = e.box.dimensions.getValue(Cesium.JulianDate.now());
              e.box.dimensions = new Cesium.Cartesian3(dim.x, dim.y, h);
              const carto = Cesium.Cartographic.fromCartesian(e.position.getValue(Cesium.JulianDate.now()));
              e.position = Cesium.Cartesian3.fromRadians(carto.longitude, carto.latitude, h / 2);
            });
          }
        });

        // initial layer visibility from the store
        useLayerStore.getState().layers.forEach((l) => { if (ds[l.id]) ds[l.id].show = l.visible; });

        viewer.camera.setView({
          destination: Cesium.Cartesian3.fromDegrees(CITY_CENTER.lon, CITY_CENTER.lat - 0.09, 9000),
          orientation: { heading: 0, pitch: Cesium.Math.toRadians(-35), roll: 0 }
        });
        setTimeout(home, 400);
        setReady(true);
        setError(null);
      } catch (err: any) {
        console.error("[cesium] init failed", err);
        setError(err?.message ?? "Cesium failed to initialise");
        setReady(false);
      }
    })();

    return () => {
      disposed = true;
      try { removeTick?.(); } catch { }
      mapBridge.unregister();
      try { viewer?.destroy?.(); } catch { }
    };
  }, [openWindow, select, setCameraText, setDrawnPath, setError, setReady]);

  /* react -> cesium sync */
  useEffect(() => {
    layers.forEach((l) => { mapBridge.setLayerVisible(l.id, l.visible); mapBridge.setLayerOpacity(l.id, l.opacity); });
  }, [layers]);

  useEffect(() => { mapBridge.setYear(year); }, [year]);
  useEffect(() => { mapBridge.setDrawMode(drawMode); }, [drawMode]);

  const ready = useMapStore((s) => s.ready);
  const error = useMapStore((s) => s.error);

  return (
    <div className="cesium-root">
      <div ref={hostRef} style={{ position: "absolute", inset: 0 }} />

      {ready && !error && (
        <div
          style={{
            position: "absolute",
            bottom: 64,
            right: 20,
            zIndex: 10,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 8,
            width: 190,
            background: "rgba(10, 16, 26, 0.92)",
            backdropFilter: "blur(16px)",
            border: "1.5px solid rgba(56, 189, 248, 0.35)",
            borderRadius: 16,
            padding: "14px 14px",
            boxShadow: "0 12px 40px rgba(0, 0, 0, 0.75)",
            userSelect: "none"
          }}
        >
          <div style={{ fontSize: 9.5, fontFamily: "monospace", letterSpacing: "0.12em", fontWeight: 700, color: "var(--txt-faint)", marginBottom: 2 }}>
            3D GLOBE CONTROLS
          </div>

          {/* D-Pad Directional Controls */}
          <div style={{ display: "flex", justifyContent: "center" }}>
            <button
              className="icon-btn"
              title="Tilt Up"
              onClick={() => mapBridge.rotateGlobe("up")}
              style={{ width: 36, height: 36, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center" }}
            >
              <ChevronUpIcon />
            </button>
          </div>

          <div style={{ display: "flex", gap: 8, alignItems: "center", justifyContent: "center" }}>
            <button
              className="icon-btn"
              title="Rotate Left"
              onClick={() => mapBridge.rotateGlobe("left")}
              style={{ width: 36, height: 36, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center" }}
            >
              <ChevronLeftIcon />
            </button>
            <button
              className={"icon-btn" + (autoSpin ? " active" : "")}
              title={autoSpin ? "Stop Globe Auto-Spin" : "Start 360° Globe Auto-Spin"}
              onClick={() => mapBridge.toggleAutoRotate()}
              style={{
                width: 38,
                height: 38,
                borderRadius: "50%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                borderColor: autoSpin ? "#38bdf8" : undefined,
                color: autoSpin ? "#38bdf8" : undefined,
                boxShadow: autoSpin ? "0 0 14px rgba(56,189,248,0.6)" : undefined
              }}
            >
              <RefreshCwIcon />
            </button>
            <button
              className="icon-btn"
              title="Rotate Right"
              onClick={() => mapBridge.rotateGlobe("right")}
              style={{ width: 36, height: 36, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center" }}
            >
              <ChevronRightIcon />
            </button>
          </div>

          <div style={{ display: "flex", justifyContent: "center" }}>
            <button
              className="icon-btn"
              title="Tilt Down"
              onClick={() => mapBridge.rotateGlobe("down")}
              style={{ width: 36, height: 36, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center" }}
            >
              <ChevronDownIcon />
            </button>
          </div>

          {/* Zoom Controls (+ and -) */}
          <div style={{ display: "flex", gap: 10, width: "100%", justifyContent: "center", marginTop: 4, paddingTop: 6, borderTop: "1px solid rgba(255,255,255,0.08)" }}>
            <button
              className="icon-btn"
              title="Zoom In (+)"
              onClick={() => mapBridge.zoomIn()}
              style={{ width: 36, height: 36, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(56,189,248,0.1)", borderColor: "rgba(56,189,248,0.3)" }}
            >
              <PlusIcon />
            </button>
            <button
              className="icon-btn"
              title="Zoom Out (-)"
              onClick={() => mapBridge.zoomOut()}
              style={{ width: 36, height: 36, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(56,189,248,0.1)", borderColor: "rgba(56,189,248,0.3)" }}
            >
              <MinusIcon />
            </button>
          </div>

          {/* Roll Controls */}
          <div style={{ display: "flex", gap: 10, width: "100%", justifyContent: "center", marginTop: 2 }}>
            <button
              className="icon-btn"
              title="Roll Counter-Clockwise"
              onClick={() => mapBridge.rotateGlobe("rollLeft")}
              style={{ width: 36, height: 36, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center" }}
            >
              <RotateCcwIcon />
            </button>
            <button
              className="icon-btn"
              title="Roll Clockwise"
              onClick={() => mapBridge.rotateGlobe("rollRight")}
              style={{ width: 36, height: 36, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center" }}
            >
              <RotateCwIcon />
            </button>
          </div>

          {/* Mode Toggle & True North Row */}
          <div style={{ display: "flex", gap: 6, width: "100%", marginTop: 4, paddingTop: 6, borderTop: "1px solid rgba(255,255,255,0.08)" }}>
            <button
              className={"btn ghost" + (viewMode === "perspective" ? " active" : "")}
              disabled={isOrbitView}
              style={{
                flex: 1,
                padding: "6px 8px",
                fontSize: 10.5,
                fontWeight: 600,
                borderRadius: 8,
                textAlign: "center",
                borderColor: isOrbitView ? "rgba(148,163,184,0.2)" : "rgba(56,189,248,0.35)",
                color: isOrbitView ? "#64748b" : viewMode === "perspective" ? "#38bdf8" : undefined,
                background: isOrbitView ? "rgba(15,23,42,0.4)" : viewMode === "perspective" ? "rgba(56,189,248,0.14)" : undefined,
                cursor: isOrbitView ? "not-allowed" : "pointer"
              }}
              title={isOrbitView ? "3D view is disabled at regional/global scale (>1,000 km)" : `Click to switch to ${viewMode === "perspective" ? "2D" : "3D"} view`}
              onClick={() => mapBridge.toggleViewMode()}
            >
              {viewMode === "perspective" ? "2D View" : "3D View"}
            </button>

            <button
              className="icon-btn"
              title="Realign camera heading to True North"
              onClick={() => mapBridge.alignNorth()}
              style={{ width: 36, height: 36, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center" }}
            >
              <CompassIcon />
            </button>
          </div>

          <button
            className="btn"
            style={{
              width: "100%",
              marginTop: 4,
              padding: "6px 10px",
              fontSize: 11,
              fontWeight: 600,
              borderRadius: 8,
              letterSpacing: "0.03em",
              background: "rgba(56, 189, 248, 0.15)",
              borderColor: "rgba(56, 189, 248, 0.4)",
              color: "#38bdf8",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 5
            }}
            title="Fly directly to city location using geodesic shortest route"
            onClick={() => mapBridge.home()}
          >
            <HomeIcon /> Home
          </button>
        </div>
      )}

      {error && (
        <div className="cesium-fallback">
          <div style={{ maxWidth: 460 }}>
            <div style={{ fontSize: 22, letterSpacing: ".2em", color: "#e2e8f0" }}>3D CITY UNAVAILABLE</div>
            <p style={{ lineHeight: 1.6, marginTop: 12 }}>
              {error}
              <br />
              <span className="mono" style={{ fontSize: 11 }}>
                The workspace, window system and all analysis panels remain fully functional.
              </span>
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
