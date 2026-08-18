/**
 * Imperative bridge between React (Zustand stores) and the Cesium viewer.
 * The viewer registers its handlers on mount; panels call mapBridge.* without
 * ever holding a reference to the Cesium instance.
 */
import type { LayerKind, ResultEntity } from "@/types";

export type LocationSpec = { lon: number; lat: number; height?: number };

export type BridgeImpl = {
  flyTo: (entityId: string) => void;
  home: () => void;
  topDown: (location?: LocationSpec) => void;
  perspectiveView: (location?: LocationSpec) => void;
  setOrientation: (mode: "perspective" | "topDown", location?: LocationSpec) => void;
  toggleViewMode: () => void;
  alignNorth: () => void;
  zoomIn: () => void;
  zoomOut: () => void;
  highlight: (ids: string[]) => void;
  setLayerVisible: (id: LayerKind, visible: boolean) => void;
  setLayerOpacity: (id: LayerKind, opacity: number) => void;
  showCandidates: (entities: ResultEntity[]) => void;
  clearCandidates: () => void;
  setYear: (year: number) => void;
  setDrawMode: (mode: string) => void;
  placeFacility: (type: string) => void;
  clearProposals: () => void;
  rotateGlobe: (dir: "up" | "down" | "left" | "right" | "rollLeft" | "rollRight") => void;
  toggleAutoRotate: () => void;
  toggleHighways: (show?: boolean) => void;
  showEmergencyRoutes: (routes: EmergencyRoute[]) => void;
  showHazard: (hazard: HazardFootprint | null) => void;
  showNetworkImpact: (impact: NetworkImpact | null) => void;
  clearEmergency: () => void;
};

/** A responder route drawn on the map: lon/lat path plus display metadata. */
export type EmergencyRoute = {
  stationId: string;
  stationName: string;
  path: [number, number][] | number[][];
  responseTimeMin: number;
  isPrimary?: boolean;
  withinTarget?: boolean;
};

/** Hazard extent as GeoJSON-ish rings in lon/lat. */
export type HazardFootprint = {
  center: [number, number] | number[];
  footprint?: { type: string; coordinates: number[][][] } | null;
  footprintMitigated?: { type: string; coordinates: number[][][] } | null;
  label?: string;
};

/** Roads the hazard closes, slows, or that a measure reopens - drawn on the map
 *  so the disruption is visible instead of being only a number in a table. */
export type NetworkImpact = {
  blocked?: number[][][];
  slowed?: number[][][];
  reopened?: number[][][];
} | null;

const noop = () => {};
let impl: Partial<BridgeImpl> = {};

export const mapBridge = {
  register(next: Partial<BridgeImpl>) { impl = next; },
  unregister() { impl = {}; },
  flyTo: (id: string) => (impl.flyTo ?? noop)(id),
  home: () => (impl.home ?? noop)(),
  topDown: (loc?: LocationSpec) => (impl.topDown ?? noop)(loc),
  perspectiveView: (loc?: LocationSpec) => (impl.perspectiveView ?? noop)(loc),
  setOrientation: (m: "perspective" | "topDown", loc?: LocationSpec) => (impl.setOrientation ?? noop)(m, loc),
  toggleViewMode: () => (impl.toggleViewMode ?? noop)(),
  alignNorth: () => (impl.alignNorth ?? noop)(),
  zoomIn: () => (impl.zoomIn ?? noop)(),
  zoomOut: () => (impl.zoomOut ?? noop)(),
  highlight: (ids: string[]) => (impl.highlight ?? noop)(ids),
  setLayerVisible: (id: LayerKind, v: boolean) => (impl.setLayerVisible ?? noop)(id, v),
  setLayerOpacity: (id: LayerKind, o: number) => (impl.setLayerOpacity ?? noop)(id, o),
  showCandidates: (e: ResultEntity[]) => (impl.showCandidates ?? noop)(e),
  clearCandidates: () => (impl.clearCandidates ?? noop)(),
  setYear: (y: number) => (impl.setYear ?? noop)(y),
  setDrawMode: (m: string) => (impl.setDrawMode ?? noop)(m),
  placeFacility: (t: string) => (impl.placeFacility ?? noop)(t),
  clearProposals: () => (impl.clearProposals ?? noop)(),
  rotateGlobe: (dir: "up" | "down" | "left" | "right" | "rollLeft" | "rollRight") => (impl.rotateGlobe ?? noop)(dir),
  toggleAutoRotate: () => (impl.toggleAutoRotate ?? noop)(),
  toggleHighways: (show?: boolean) => (impl.toggleHighways ?? noop)(show),
  showEmergencyRoutes: (r: EmergencyRoute[]) => (impl.showEmergencyRoutes ?? noop)(r),
  showHazard: (h: HazardFootprint | null) => (impl.showHazard ?? noop)(h),
  showNetworkImpact: (n: NetworkImpact) => (impl.showNetworkImpact ?? noop)(n),
  clearEmergency: () => (impl.clearEmergency ?? noop)()
};
