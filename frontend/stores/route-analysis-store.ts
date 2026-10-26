import { create } from "zustand";
import type {
  AffectedNetworkPreview,
  DataMode,
  DisasterScenarioConfig,
  LoadedStudyAreaDataset,
  MapInteractionMode,
  RoadNetworkSegment,
  RouteComparisonResult,
  RouteCostMetric,
  RouteWaypoint,
  StudyAreaBuilding,
  StudyAreaId,
  StudyAreaLandmark,
  WaterwayFeature,
  WizardStepNumber,
} from "../types/route-analysis.ts";
import {
  STUDY_AREAS,
  buildRoadGraph,
  buildSyntheticBenchmarkDataset,
  classifyScenarioOnGraph,
  compareRoutesOnGraph,
  computeInputSignature,
  createPresetScenarios,
  validateHazardPolygon,
  type RoadGraph,
} from "../lib/routing-engine.ts";
import { api, probeBackendStatus } from "../lib/api/client";

export interface BackendConnectionState {
  checked: boolean;
  checking: boolean;
  apiReachable: boolean;
  dbReady: boolean;
  detail: string;
}

interface RouteAnalysisState {
  // Navigation & layout
  workspaceView: "overview" | "map";
  leftPanelOpen: boolean;
  rightPanelOpen: boolean;
  legendOpen: boolean;
  wizardStep: WizardStepNumber;

  // Data mode & backend status
  dataMode: DataMode;
  backendStatus: BackendConnectionState;

  // Study area & loaded network
  studyAreaId: StudyAreaId;
  datasets: Partial<Record<StudyAreaId, LoadedStudyAreaDataset>>;
  graphs: Partial<Record<StudyAreaId, RoadGraph>>;
  datasetLoading: boolean;
  datasetError: string | null;

  // Waypoints
  origin: RouteWaypoint | null;
  destination: RouteWaypoint | null;

  // Scenarios
  scenarios: DisasterScenarioConfig[];
  activeScenarioId: string;
  draftScenario: DisasterScenarioConfig;
  scenarioDirty: boolean;

  // Map interaction & polygon drawing
  interactionMode: MapInteractionMode;
  drawingVertices: [number, number][];

  // Routing settings & live preview
  costMetric: RouteCostMetric;
  affectedPreview: AffectedNetworkPreview | null;
  scenarioValidationError: string | null;

  // Execution & results
  analysisStatus: "idle" | "running" | "success" | "error";
  analysisError: string | null;
  result: RouteComparisonResult | null;
  recentRuns: RouteComparisonResult[];

  // Actions
  setWorkspaceView: (view: "overview" | "map") => void;
  setLeftPanelOpen: (open: boolean) => void;
  setRightPanelOpen: (open: boolean) => void;
  setLegendOpen: (open: boolean) => void;
  setWizardStep: (step: WizardStepNumber) => void;

  refreshBackendStatus: () => Promise<void>;
  setDataMode: (mode: DataMode) => void;

  loadStudyArea: (studyAreaId: StudyAreaId) => Promise<void>;
  setOrigin: (wp: RouteWaypoint | null) => void;
  setDestination: (wp: RouteWaypoint | null) => void;
  swapWaypoints: () => void;
  clearWaypoints: () => void;

  selectScenario: (scenarioId: string) => void;
  updateDraftScenario: (patch: Partial<DisasterScenarioConfig>) => void;
  saveScenario: (asNew?: boolean) => void;
  cancelScenarioEdits: () => void;
  toggleRoadInScenario: (roadId: string) => void;

  setInteractionMode: (mode: MapInteractionMode) => void;
  addDrawingVertex: (lon: number, lat: number) => void;
  undoDrawingVertex: () => void;
  clearDrawingVertices: () => void;
  finishDrawingPolygon: () => { ok: boolean; error?: string };
  handleMapCoordinateClick: (lon: number, lat: number) => void;

  setCostMetric: (metric: RouteCostMetric) => void;
  runRouteAnalysis: () => Promise<void>;
  loadSampleAndStart: (scenarioId?: string) => Promise<void>;
  resetDemo: () => Promise<void>;

  getCurrentSignature: () => string;
  isResultStale: () => boolean;
  getReadinessValidation: () => { valid: boolean; reasons: string[] };
}

let inFlightAbort: AbortController | null = null;
let latestRequestSeq = 0;

function computePreviewSafe(
  graph: RoadGraph | undefined,
  scenario: DisasterScenarioConfig
): { preview: AffectedNetworkPreview | null; error: string | null } {
  if (!graph) {
    return { preview: null, error: null };
  }
  try {
    const { preview } = classifyScenarioOnGraph(graph, scenario);
    return { preview, error: null };
  } catch (err: any) {
    return {
      preview: null,
      error: err?.message || "Invalid scenario configuration.",
    };
  }
}

const initialPresets = createPresetScenarios();
const defaultScenario = initialPresets[0];
const defaultStudyArea = STUDY_AREAS.panvel_kalundre_osm;

export const useRouteAnalysisStore = create<RouteAnalysisState>((set, get) => ({
  workspaceView: "map",
  leftPanelOpen: true,
  rightPanelOpen: false,
  legendOpen: true,
  wizardStep: 1,

  dataMode: "demo",
  backendStatus: {
    checked: false,
    checking: false,
    apiReachable: false,
    dbReady: false,
    detail: "Checking backend connection...",
  },

  studyAreaId: "panvel_kalundre_osm",
  datasets: {},
  graphs: {},
  datasetLoading: false,
  datasetError: null,

  origin: { ...defaultStudyArea.defaultOrigin },
  destination: { ...defaultStudyArea.defaultDestination },

  scenarios: initialPresets,
  activeScenarioId: defaultScenario.id,
  draftScenario: structuredClone(defaultScenario),
  scenarioDirty: false,

  interactionMode: "navigate",
  drawingVertices: [],

  costMetric: "time",
  affectedPreview: null,
  scenarioValidationError: null,

  analysisStatus: "idle",
  analysisError: null,
  result: null,
  recentRuns: [],

  setWorkspaceView: (workspaceView) => set({ workspaceView }),
  setLeftPanelOpen: (leftPanelOpen) => set({ leftPanelOpen }),
  setRightPanelOpen: (rightPanelOpen) => set({ rightPanelOpen }),
  setLegendOpen: (legendOpen) => set({ legendOpen }),
  setWizardStep: (wizardStep) => set({ wizardStep }),

  refreshBackendStatus: async () => {
    set((s) => ({
      backendStatus: { ...s.backendStatus, checking: true },
    }));
    const probe = await probeBackendStatus();
    set((s) => ({
      backendStatus: {
        checked: true,
        checking: false,
        apiReachable: probe.apiReachable,
        dbReady: probe.dbReady,
        detail: probe.detail,
      },
      // Automatically switch to live only on initial check if DB is genuinely ready
      dataMode:
        !s.backendStatus.checked && probe.dbReady && s.studyAreaId === "panvel_kalundre_osm"
          ? "live"
          : !probe.dbReady && s.dataMode === "live" && !s.backendStatus.checked
          ? "demo"
          : s.dataMode,
    }));
  },

  setDataMode: (mode) => {
    if (inFlightAbort) {
      inFlightAbort.abort();
      inFlightAbort = null;
    }
    set((s) => ({
      dataMode: mode,
      analysisStatus: s.analysisStatus === "running" ? "idle" : s.analysisStatus,
      analysisError: null,
    }));
  },

  loadStudyArea: async (studyAreaId) => {
    if (inFlightAbort) {
      inFlightAbort.abort();
      inFlightAbort = null;
    }

    const existingDataset = get().datasets[studyAreaId];
    const existingGraph = get().graphs[studyAreaId];
    const areaDef = STUDY_AREAS[studyAreaId];

    // Pick first scenario matching this study area
    const matchingScenario =
      get().scenarios.find((sc) => sc.studyAreaId === studyAreaId) ??
      get().scenarios[0];

    set({
      studyAreaId,
      origin: { ...areaDef.defaultOrigin },
      destination: { ...areaDef.defaultDestination },
      activeScenarioId: matchingScenario.id,
      draftScenario: structuredClone(matchingScenario),
      scenarioDirty: false,
      interactionMode: "navigate",
      drawingVertices: [],
      analysisError: null,
      // Synthetic benchmark grid is local-only
      dataMode: areaDef.isSyntheticBenchmark ? "demo" : get().dataMode,
    });

    if (existingDataset && existingGraph) {
      const { preview, error } = computePreviewSafe(
        existingGraph,
        get().draftScenario
      );
      set({
        affectedPreview: preview,
        scenarioValidationError: error,
        datasetLoading: false,
        datasetError: null,
      });
      return;
    }

    set({ datasetLoading: true, datasetError: null });

    try {
      let dataset: LoadedStudyAreaDataset;
      if (studyAreaId === "pilot_synthetic_grid") {
        dataset = buildSyntheticBenchmarkDataset();
      } else {
        const res = await fetch("/data/panvel-osm-demo.json");
        if (!res.ok) {
          throw new Error(
            `Failed to load study area road network (HTTP ${res.status})`
          );
        }
        const raw = await res.json();
        const roads: RoadNetworkSegment[] = Array.isArray(raw.roads)
          ? raw.roads
          : [];
        const waterways: WaterwayFeature[] = Array.isArray(raw.waterways)
          ? raw.waterways
          : [];
        const rawFacs: StudyAreaLandmark[] = Array.isArray(raw.facilities)
          ? raw.facilities
          : [];
        const rawLms: StudyAreaLandmark[] = Array.isArray(raw.landmarks)
          ? raw.landmarks
          : [];
        const buildings: StudyAreaBuilding[] = Array.isArray(raw.buildings)
          ? raw.buildings
          : [];
        const graphBuilt = buildRoadGraph(roads);
        dataset = {
          studyAreaId: "panvel_kalundre_osm",
          roads,
          waterways,
          landmarks: [...rawLms, ...rawFacs],
          buildings,
          nodeCount: graphBuilt.routableCore.size,
          directedEdgeCount: graphBuilt.edges.length,
        };
        const { preview, error } = computePreviewSafe(
          graphBuilt,
          get().draftScenario
        );
        set((s) => ({
          datasets: { ...s.datasets, [studyAreaId]: dataset },
          graphs: { ...s.graphs, [studyAreaId]: graphBuilt },
          affectedPreview: preview,
          scenarioValidationError: error,
          datasetLoading: false,
          datasetError: null,
        }));
        return;
      }

      const graphBuilt = buildRoadGraph(dataset.roads);
      const { preview, error } = computePreviewSafe(
        graphBuilt,
        get().draftScenario
      );
      set((s) => ({
        datasets: { ...s.datasets, [studyAreaId]: dataset },
        graphs: { ...s.graphs, [studyAreaId]: graphBuilt },
        affectedPreview: preview,
        scenarioValidationError: error,
        datasetLoading: false,
        datasetError: null,
      }));
    } catch (err: any) {
      set({
        datasetLoading: false,
        datasetError:
          err?.message || "Failed to load study area network dataset.",
      });
    }
  },

  setOrigin: (origin) =>
    set((s) => ({
      origin,
      interactionMode:
        s.interactionMode === "pick_origin" ? "navigate" : s.interactionMode,
      analysisError: null,
    })),

  setDestination: (destination) =>
    set((s) => ({
      destination,
      interactionMode:
        s.interactionMode === "pick_destination"
          ? "navigate"
          : s.interactionMode,
      analysisError: null,
    })),

  swapWaypoints: () =>
    set((s) => ({
      origin: s.destination ? { ...s.destination } : null,
      destination: s.origin ? { ...s.origin } : null,
      analysisError: null,
    })),

  clearWaypoints: () =>
    set({
      origin: null,
      destination: null,
      analysisError: null,
    }),

  selectScenario: (scenarioId) => {
    const found = get().scenarios.find((sc) => sc.id === scenarioId);
    if (!found) return;
    const draft = structuredClone(found);
    const graph = get().graphs[get().studyAreaId];
    const { preview, error } = computePreviewSafe(graph, draft);
    set({
      activeScenarioId: found.id,
      draftScenario: draft,
      scenarioDirty: false,
      drawingVertices: [],
      interactionMode: "navigate",
      affectedPreview: preview,
      scenarioValidationError: error,
      analysisError: null,
    });
  },

  updateDraftScenario: (patch) => {
    const nextDraft: DisasterScenarioConfig = {
      ...get().draftScenario,
      ...patch,
      updatedAt: new Date().toISOString(),
    };
    const graph = get().graphs[get().studyAreaId];
    const { preview, error } = computePreviewSafe(graph, nextDraft);
    set({
      draftScenario: nextDraft,
      scenarioDirty: true,
      affectedPreview: preview,
      scenarioValidationError: error,
      analysisError: null,
    });
  },

  saveScenario: (asNew = false) => {
    const { draftScenario, scenarios } = get();
    const saved: DisasterScenarioConfig = {
      ...structuredClone(draftScenario),
      id:
        asNew || draftScenario.isPreset
          ? `custom_${Date.now().toString(36)}`
          : draftScenario.id,
      isPreset: false,
      name:
        asNew || draftScenario.isPreset
          ? draftScenario.name.endsWith("(Custom)")
            ? draftScenario.name
            : `${draftScenario.name}`
          : draftScenario.name,
      updatedAt: new Date().toISOString(),
    };
    const existsIdx = scenarios.findIndex((s) => s.id === saved.id);
    const nextList =
      existsIdx >= 0
        ? scenarios.map((s, idx) => (idx === existsIdx ? saved : s))
        : [saved, ...scenarios];

    set({
      scenarios: nextList,
      activeScenarioId: saved.id,
      draftScenario: structuredClone(saved),
      scenarioDirty: false,
    });
  },

  cancelScenarioEdits: () => {
    const active = get().scenarios.find(
      (sc) => sc.id === get().activeScenarioId
    );
    if (!active) return;
    const restored = structuredClone(active);
    const graph = get().graphs[get().studyAreaId];
    const { preview, error } = computePreviewSafe(graph, restored);
    set({
      draftScenario: restored,
      scenarioDirty: false,
      drawingVertices: [],
      interactionMode: "navigate",
      affectedPreview: preview,
      scenarioValidationError: error,
    });
  },

  toggleRoadInScenario: (roadId) => {
    if (!roadId) return;
    const cur = get().draftScenario.affectedRoadIds;
    const nextIds = cur.includes(roadId)
      ? cur.filter((id) => id !== roadId)
      : [...cur, roadId];
    get().updateDraftScenario({ affectedRoadIds: nextIds });
  },

  setInteractionMode: (interactionMode) =>
    set((s) => ({
      interactionMode,
      drawingVertices:
        interactionMode === "draw_hazard_polygon" ? [] : s.drawingVertices,
    })),

  addDrawingVertex: (lon, lat) =>
    set((s) => ({
      drawingVertices: [
        ...s.drawingVertices,
        [Number(lon.toFixed(6)), Number(lat.toFixed(6))],
      ],
    })),

  undoDrawingVertex: () =>
    set((s) => ({
      drawingVertices: s.drawingVertices.slice(0, -1),
    })),

  clearDrawingVertices: () => set({ drawingVertices: [] }),

  finishDrawingPolygon: () => {
    const verts = get().drawingVertices;
    const err = validateHazardPolygon(verts);
    if (err) {
      return { ok: false, error: err };
    }
    const cx =
      verts.reduce((acc, v) => acc + v[0], 0) / Math.max(1, verts.length);
    const cy =
      verts.reduce((acc, v) => acc + v[1], 0) / Math.max(1, verts.length);
    get().updateDraftScenario({
      active: true,
      geometryKind: "polygon",
      polygon: [...verts],
      center: [Number(cx.toFixed(6)), Number(cy.toFixed(6))],
    });
    set({ interactionMode: "navigate", drawingVertices: [] });
    return { ok: true };
  },

  handleMapCoordinateClick: (lon, lat) => {
    const mode = get().interactionMode;
    const cleanLon = Number(lon.toFixed(6));
    const cleanLat = Number(lat.toFixed(6));

    if (mode === "pick_origin") {
      get().setOrigin({
        lon: cleanLon,
        lat: cleanLat,
        label: `Map Point (${cleanLat.toFixed(4)}°N, ${cleanLon.toFixed(4)}°E)`,
        source: "map_click",
      });
    } else if (mode === "pick_destination") {
      get().setDestination({
        lon: cleanLon,
        lat: cleanLat,
        label: `Map Point (${cleanLat.toFixed(4)}°N, ${cleanLon.toFixed(4)}°E)`,
        source: "map_click",
      });
    } else if (mode === "draw_hazard_polygon") {
      get().addDrawingVertex(cleanLon, cleanLat);
    } else if (mode === "pick_hazard_center") {
      get().updateDraftScenario({
        active: true,
        geometryKind: "circle",
        center: [cleanLon, cleanLat],
      });
      set({ interactionMode: "navigate" });
    }
  },

  setCostMetric: (costMetric) => set({ costMetric, analysisError: null }),

  getReadinessValidation: () => {
    const s = get();
    const reasons: string[] = [];
    if (s.datasetLoading) {
      reasons.push("Study area road network is still loading.");
    }
    if (s.datasetError) {
      reasons.push(s.datasetError);
    }
    if (!s.origin) {
      reasons.push("Select an Origin point (Step 2).");
    }
    if (!s.destination) {
      reasons.push("Select a Destination point (Step 2).");
    }
    if (
      s.origin &&
      s.destination &&
      Math.abs(s.origin.lon - s.destination.lon) < 1e-6 &&
      Math.abs(s.origin.lat - s.destination.lat) < 1e-6
    ) {
      reasons.push("Origin and Destination must be two distinct locations.");
    }
    if (!s.draftScenario.name.trim()) {
      reasons.push("Scenario name cannot be empty (Step 3).");
    }
    if (
      !Number.isFinite(s.draftScenario.penaltyMultiplier) ||
      s.draftScenario.penaltyMultiplier < 1.0
    ) {
      reasons.push("Penalty multiplier must be >= 1.0 (Step 3).");
    }
    if (s.scenarioValidationError) {
      reasons.push(s.scenarioValidationError);
    }
    if (s.interactionMode === "draw_hazard_polygon") {
      reasons.push("Finish or cancel the polygon currently being drawn on the map.");
    }
    return { valid: reasons.length === 0, reasons };
  },

  runRouteAnalysis: async () => {
    const s = get();
    if (s.analysisStatus === "running") {
      return; // Prevent duplicate clicks
    }

    const readiness = s.getReadinessValidation();
    if (!readiness.valid || !s.origin || !s.destination) {
      set({
        analysisStatus: "error",
        analysisError: readiness.reasons[0] || "Invalid route analysis inputs.",
      });
      return;
    }

    if (inFlightAbort) {
      inFlightAbort.abort();
    }
    const ctrl = new AbortController();
    inFlightAbort = ctrl;
    const reqSeq = ++latestRequestSeq;

    const studyArea = STUDY_AREAS[s.studyAreaId];
    const originSnapshot = { ...s.origin };
    const destSnapshot = { ...s.destination };
    const scenarioSnapshot = structuredClone(s.draftScenario);
    const costMetricSnapshot = s.costMetric;
    const modeSnapshot = s.dataMode;

    set({ analysisStatus: "running", analysisError: null });

    try {
      let computed: RouteComparisonResult;

      if (modeSnapshot === "live" && !studyArea.isSyntheticBenchmark) {
        // Strictly execute against live FastAPI + PostGIS backend; never fake on error
        computed = await api.compareDisasterRoutes({
          studyArea,
          origin: originSnapshot,
          destination: destSnapshot,
          scenario: scenarioSnapshot,
          costMetric: costMetricSnapshot,
          signal: ctrl.signal,
        });
      } else {
        // Ensure local graph is loaded
        let graph = get().graphs[s.studyAreaId];
        if (!graph) {
          await get().loadStudyArea(s.studyAreaId);
          graph = get().graphs[s.studyAreaId];
        }
        if (!graph) {
          throw new Error("Local road network graph is unavailable.");
        }
        computed = compareRoutesOnGraph({
          graph,
          studyArea,
          origin: originSnapshot,
          destination: destSnapshot,
          scenario: scenarioSnapshot,
          costMetric: costMetricSnapshot,
          dataMode: "demo",
        });
      }

      if (reqSeq !== latestRequestSeq || ctrl.signal.aborted) {
        return; // Stale request discarded
      }

      set((prev) => ({
        analysisStatus: "success",
        analysisError: null,
        result: computed,
        rightPanelOpen: true,
        wizardStep: 6,
        recentRuns: [computed, ...prev.recentRuns].slice(0, 6),
      }));
    } catch (err: any) {
      if (
        reqSeq !== latestRequestSeq ||
        ctrl.signal.aborted ||
        err?.message === "REQUEST_CANCELLED"
      ) {
        return;
      }
      set({
        analysisStatus: "error",
        analysisError:
          err?.message || "Route comparison failed due to an unexpected error.",
      });
    } finally {
      if (inFlightAbort === ctrl) {
        inFlightAbort = null;
      }
    }
  },

  loadSampleAndStart: async (scenarioId = "preset_kalundre_flood") => {
    const targetScenario =
      get().scenarios.find((sc) => sc.id === scenarioId) ?? get().scenarios[0];
    if (get().studyAreaId !== targetScenario.studyAreaId || !get().graphs[targetScenario.studyAreaId]) {
      await get().loadStudyArea(targetScenario.studyAreaId);
    }
    const areaDef = STUDY_AREAS[targetScenario.studyAreaId];
    get().selectScenario(targetScenario.id);
    set({
      workspaceView: "map",
      leftPanelOpen: true,
      origin: { ...areaDef.defaultOrigin },
      destination: { ...areaDef.defaultDestination },
      wizardStep: 5,
    });
    await get().runRouteAnalysis();
  },

  resetDemo: async () => {
    if (inFlightAbort) {
      inFlightAbort.abort();
      inFlightAbort = null;
    }
    latestRequestSeq++;
    const freshPresets = createPresetScenarios();
    const first = freshPresets[0];
    const area = STUDY_AREAS.panvel_kalundre_osm;

    set({
      workspaceView: "map",
      leftPanelOpen: true,
      rightPanelOpen: false,
      legendOpen: true,
      wizardStep: 1,
      dataMode: get().backendStatus.dbReady ? "live" : "demo",
      studyAreaId: "panvel_kalundre_osm",
      origin: { ...area.defaultOrigin },
      destination: { ...area.defaultDestination },
      scenarios: freshPresets,
      activeScenarioId: first.id,
      draftScenario: structuredClone(first),
      scenarioDirty: false,
      interactionMode: "navigate",
      drawingVertices: [],
      costMetric: "time",
      analysisStatus: "idle",
      analysisError: null,
      result: null,
    });

    await get().loadStudyArea("panvel_kalundre_osm");
  },

  getCurrentSignature: () => {
    const s = get();
    return computeInputSignature({
      studyAreaId: s.studyAreaId,
      origin: s.origin,
      destination: s.destination,
      scenario: s.draftScenario,
      costMetric: s.costMetric,
      dataMode: s.dataMode,
    });
  },

  isResultStale: () => {
    const s = get();
    if (!s.result) return false;
    return s.result.provenance.inputSignature !== s.getCurrentSignature();
  },
}));
