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
import EmergencyPanel from "@/components/panels/EmergencyPanel";
import JobMonitorPanel from "@/components/panels/JobMonitorPanel";
import ComparisonPanel from "@/components/panels/ComparisonPanel";
import AIPanel from "@/components/panels/AIPanel";
import AgentTracePanel from "@/components/panels/AgentTracePanel";
import RegionsPanel from "@/components/panels/RegionsPanel";
import ScorecardPanel from "@/components/panels/ScorecardPanel";
import DevelopmentPanel from "@/components/panels/DevelopmentPanel";

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
  emergency: EmergencyPanel,
  regions: RegionsPanel,
  scorecard: ScorecardPanel,
  development: DevelopmentPanel,
  jobs: JobMonitorPanel,
  comparison: ComparisonPanel,
  ai: AIPanel,
  trace: AgentTracePanel
};
