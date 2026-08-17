"use client";
import type { WindowId } from "@/stores/window-store";
import CityPanel from "@/components/panels/CityPanel";
import LayersPanel from "@/components/panels/LayersPanel";
import LegendPanel from "@/components/panels/LegendPanel";
import InspectorPanel from "@/components/panels/InspectorPanel";
import ScenarioPanel from "@/components/panels/ScenarioPanel";
import ChangesPanel from "@/components/panels/ChangesPanel";
import PlanningPanel from "@/components/panels/PlanningPanel";
import AnalysisPanel from "@/components/panels/AnalysisPanel";
import ResultsPanel from "@/components/panels/ResultsPanel";
import SimulationPanel from "@/components/panels/SimulationPanel";
import JobMonitorPanel from "@/components/panels/JobMonitorPanel";
import ComparisonPanel from "@/components/panels/ComparisonPanel";
import AIPanel from "@/components/panels/AIPanel";
import AgentTracePanel from "@/components/panels/AgentTracePanel";

export const WINDOW_CONTENT: Record<WindowId, React.ComponentType> = {
  city: CityPanel,
  layers: LayersPanel,
  legend: LegendPanel,
  inspector: InspectorPanel,
  scenario: ScenarioPanel,
  changes: ChangesPanel,
  planning: PlanningPanel,
  analysis: AnalysisPanel,
  results: ResultsPanel,
  simulation: SimulationPanel,
  jobs: JobMonitorPanel,
  comparison: ComparisonPanel,
  ai: AIPanel,
  trace: AgentTracePanel
};
