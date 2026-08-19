"use client";

import type { WindowId } from "@/stores/window-store";
import type { LayerKind } from "@/types";

export type WorkflowId =
  | "plan"
  | "stress"
  | "improve"
  | "compare"
  | "explain";

export type WorkflowStepDef = {
  id: string;
  label: string;
  shortLabel: string;
  description: string;
  actionPrompt: string;
  actionLabel: string;
  targetWindow: WindowId;
  auxWindows?: WindowId[];
  relevantLayers?: LayerKind[];
};

export type WorkflowDef = {
  id: WorkflowId;
  title: string;
  shortTitle: string;
  icon: string;
  badge: string;
  outcome: string;
  summary: string;
  relevantLayers: LayerKind[];
  steps: WorkflowStepDef[];
};

export const WORKFLOWS: Record<WorkflowId, WorkflowDef> = {
  plan: {
    id: "plan",
    title: "Plan Infrastructure",
    shortTitle: "Plan",
    icon: "⚒",
    badge: "Site & Network Planning",
    summary:
      "Define requirements, evaluate candidate sites or road alignments, validate constraints, and commit interventions to a scenario.",
    outcome:
      "Turn requirements into a validated, constraint-checked scenario change set.",
    relevantLayers: ["parcels", "facilities", "flood", "roads", "candidates", "proposals"],
    steps: [
      {
        id: "requirement",
        label: "Define Requirement",
        shortLabel: "Define",
        description:
          "Specify facility type, capacity, land area, service catchment, and criteria weights.",
        actionPrompt: "Configure planning parameters and search for suitable candidate sites.",
        actionLabel: "Generate Candidates",
        targetWindow: "planning",
        auxWindows: ["layers"],
        relevantLayers: ["parcels", "facilities", "flood"]
      },
      {
        id: "candidates",
        label: "Evaluate Candidates",
        shortLabel: "Evaluate",
        description:
          "Review scored candidates with KPI breakdown, suitability trade-offs, and map markers.",
        actionPrompt: "Review ranked candidate sites and inspect the top recommendation.",
        actionLabel: "Inspect Candidate",
        targetWindow: "results",
        auxWindows: ["analysis", "inspector"],
        relevantLayers: ["candidates", "parcels", "flood"]
      },
      {
        id: "place",
        label: "Inspect in 3D Twin",
        shortLabel: "Inspect 3D",
        description:
          "Fly to the parcel, examine spatial context, zoning, elevation, and surrounding amenities.",
        actionPrompt: "Inspect parcel in 3D Cesium twin and verify local site characteristics.",
        actionLabel: "Validate Constraints",
        targetWindow: "inspector",
        auxWindows: ["results"],
        relevantLayers: ["parcels", "buildings", "facilities"]
      },
      {
        id: "validate",
        label: "Validate Constraints",
        shortLabel: "Validate",
        description:
          "Run feasibility checks on slope, flood exclusion, zoning compliance, and same-type proximity.",
        actionPrompt: "Verify all environmental and regulatory constraints before commitment.",
        actionLabel: "Add to Scenario",
        targetWindow: "analysis",
        auxWindows: ["results", "changes"],
        relevantLayers: ["flood", "landuse", "parcels"]
      },
      {
        id: "save",
        label: "Commit Scenario Change",
        shortLabel: "Commit",
        description:
          "Save approved intervention to active scenario basket and review aggregate plan impact.",
        actionPrompt: "Scenario updated. Stress-test the new plan against disaster hazards.",
        actionLabel: "Stress-Test Plan",
        targetWindow: "changes",
        auxWindows: ["scenario", "simulation"],
        relevantLayers: ["proposals", "facilities", "roads"]
      }
    ]
  },

  stress: {
    id: "stress",
    title: "Stress-Test the Plan",
    shortTitle: "Stress-Test",
    icon: "▶",
    badge: "Resilience & Disaster",
    summary:
      "Simulate hazard events (floods, infrastructure failures), detect blocked links, evaluate emergency access, and apply mitigation packages.",
    outcome:
      "Quantify disaster failure modes, emergency response reachability, and resilience deltas.",
    relevantLayers: ["flood", "roads", "facilities", "population"],
    steps: [
      {
        id: "scenario",
        label: "Select Scenario & Baseline",
        shortLabel: "Scenario",
        description:
          "Choose the infrastructure plan to stress-test against baseline city conditions.",
        actionPrompt: "Confirm the active scenario to be tested under disaster conditions.",
        actionLabel: "Configure Disaster",
        targetWindow: "scenario",
        auxWindows: ["changes"],
        relevantLayers: ["proposals", "facilities"]
      },
      {
        id: "hazard",
        label: "Simulate Disaster Event",
        shortLabel: "Disaster Sim",
        description:
          "Simulate 50-year/100-year flood or localized hazards with depth and footprint exposure.",
        actionPrompt: "Run hazard simulation to calculate inundation footprints and network disruption.",
        actionLabel: "Analyze Blocked Links",
        targetWindow: "simulation",
        auxWindows: ["emergency"],
        relevantLayers: ["flood", "roads", "population"]
      },
      {
        id: "blocked",
        label: "Detect Blocked Infrastructure",
        shortLabel: "Failures",
        description:
          "Identify flooded roads, cut-off wards, offline facilities, and exposed population.",
        actionPrompt: "Examine blocked arterial roads and stranded facility catchments.",
        actionLabel: "Reroute Emergency Units",
        targetWindow: "emergency",
        auxWindows: ["analysis", "results"],
        relevantLayers: ["flood", "roads", "facilities"]
      },
      {
        id: "reroute",
        label: "Emergency Response & Rerouting",
        shortLabel: "Reroute",
        description:
          "Compute dynamic response routing around blocked links from nearest operational stations.",
        actionPrompt: "Evaluate responder travel times and identify areas exceeding target response window.",
        actionLabel: "Apply Mitigations",
        targetWindow: "emergency",
        auxWindows: ["inspector"],
        relevantLayers: ["roads", "facilities"]
      },
      {
        id: "mitigate",
        label: "Resilience Delta & Mitigation",
        shortLabel: "Resilience",
        description:
          "Apply flood barriers, drainage pumps, or road elevations and quantify recovery deltas.",
        actionPrompt: "Review resilience improvements and commit mitigation measures to scenario.",
        actionLabel: "Save Mitigation Plan",
        targetWindow: "emergency",
        auxWindows: ["changes", "comparison"],
        relevantLayers: ["flood", "roads", "proposals"]
      }
    ]
  },

  improve: {
    id: "improve",
    title: "Improve the City",
    shortTitle: "Improve",
    icon: "⌗",
    badge: "Gap Detection & Upgrades",
    summary:
      "Score city baseline, detect underserved zones and capacity deficits, generate intervention packages, and measure overall score gains.",
    outcome:
      "Transform detected service gaps into a coordinated, multi-facility development package.",
    relevantLayers: ["population", "facilities", "landuse", "roads"],
    steps: [
      {
        id: "score",
        label: "Baseline City Audit",
        shortLabel: "Audit",
        description:
          "Calculate baseline accessibility, facility coverage, and travel time across all wards.",
        actionPrompt: "Audit current city infrastructure scores and baseline indicators.",
        actionLabel: "Detect Service Gaps",
        targetWindow: "analysis",
        auxWindows: ["city"],
        relevantLayers: ["facilities", "population", "roads"]
      },
      {
        id: "gaps",
        label: "Detect Infrastructure Gaps",
        shortLabel: "Gaps",
        description:
          "Identify wards with severe healthcare, educational, or emergency coverage deficits.",
        actionPrompt: "Locate underserved populations requiring new facility or road investments.",
        actionLabel: "Build Intervention Package",
        targetWindow: "planning",
        auxWindows: ["analysis"],
        relevantLayers: ["population", "parcels", "facilities"]
      },
      {
        id: "package",
        label: "Build Development Package",
        shortLabel: "Package",
        description:
          "Bundle optimal facility sites and arterial road proposals into a unified scenario change set.",
        actionPrompt: "Review proposed city package interventions and estimated capital expenditure.",
        actionLabel: "Simulate Growth & Impact",
        targetWindow: "changes",
        auxWindows: ["planning"],
        relevantLayers: ["proposals", "parcels", "roads"]
      },
      {
        id: "simulate",
        label: "Simulate Future Horizon",
        shortLabel: "Simulate",
        description:
          "Project population growth and test package performance against 2035/2040 horizon demands.",
        actionPrompt: "Run demographic and capacity simulations with proposed interventions active.",
        actionLabel: "Compare with Baseline",
        targetWindow: "simulation",
        auxWindows: ["analysis"],
        relevantLayers: ["population", "proposals"]
      },
      {
        id: "compare",
        label: "Compare with Baseline",
        shortLabel: "Compare",
        description:
          "Measure accessibility gains, population served, and resilience improvements over baseline.",
        actionPrompt: "Confirm net positive city transformation and commit package to scenario.",
        actionLabel: "Commit Approved Package",
        targetWindow: "comparison",
        auxWindows: ["changes", "results"],
        relevantLayers: ["proposals", "facilities", "roads"]
      }
    ]
  },

  compare: {
    id: "compare",
    title: "Compare Plans (A/B/C)",
    shortTitle: "Compare",
    icon: "⚖",
    badge: "Multi-Scenario Trade-offs",
    summary:
      "Evaluate multiple scenario variants using unified evaluation criteria, ranking matrices, and trade-off explanations.",
    outcome:
      "Deliver an authoritative, data-backed selection between alternative master plans.",
    relevantLayers: ["proposals", "facilities", "roads", "flood"],
    steps: [
      {
        id: "variants",
        label: "Select Scenario Variants",
        shortLabel: "Select Plans",
        description:
          "Choose Plan A, Plan B, and Plan C variants representing different planning strategies.",
        actionPrompt: "Select distinct scenario proposals to compare side-by-side.",
        actionLabel: "Run Common Metrics",
        targetWindow: "scenario",
        auxWindows: ["comparison"],
        relevantLayers: ["proposals", "facilities"]
      },
      {
        id: "metrics",
        label: "Evaluate Common Metrics",
        shortLabel: "Common Metrics",
        description:
          "Compute accessibility, resilience, capital cost, and population coverage under identical assumptions.",
        actionPrompt: "Execute deterministic multi-criteria comparison on the backend engine.",
        actionLabel: "View Trade-Off Matrix",
        targetWindow: "analysis",
        auxWindows: ["comparison"],
        relevantLayers: ["roads", "facilities", "flood"]
      },
      {
        id: "compare",
        label: "Trade-Off & Matrix Analysis",
        shortLabel: "Trade-offs",
        description:
          "Examine score deltas, cost vs coverage trade-offs, and risk exposure across variants.",
        actionPrompt: "Review ranked matrix and algorithmically identified winning plan.",
        actionLabel: "Select Preferred Plan",
        targetWindow: "comparison",
        auxWindows: ["results"],
        relevantLayers: ["proposals", "roads"]
      },
      {
        id: "decision",
        label: "Commit & Explain Selection",
        shortLabel: "Decision",
        description:
          "Set preferred plan as active working scenario and export grounded decision rationale.",
        actionPrompt: "Preferred plan activated. Stress-test or generate comprehensive decision report.",
        actionLabel: "Explain Decision Record",
        targetWindow: "results",
        auxWindows: ["ai", "changes"],
        relevantLayers: ["proposals", "facilities"]
      }
    ]
  },

  explain: {
    id: "explain",
    title: "Explain Results & Rationale",
    shortTitle: "Explain",
    icon: "✦",
    badge: "Decision Intelligence & Audit",
    summary:
      "Translate raw engine results into planner-ready KPI breakdowns, constraint audits, population impact charts, and decision records.",
    outcome:
      "Produce a grounded, transparent decision record with clear trade-offs and limitations.",
    relevantLayers: ["parcels", "facilities", "flood", "population"],
    steps: [
      {
        id: "recommendation",
        label: "Preferred Option & Score",
        shortLabel: "Recommendation",
        description:
          "Display top-ranked recommendation, overall composite score, and primary value drivers.",
        actionPrompt: "Inspect the primary recommendation and key performance indicators.",
        actionLabel: "View Score Breakdown",
        targetWindow: "results",
        auxWindows: ["inspector"],
        relevantLayers: ["candidates", "parcels"]
      },
      {
        id: "breakdown",
        label: "KPI & Criteria Breakdown",
        shortLabel: "Breakdown",
        description:
          "Inspect individual criterion scores (travel time, slope, flood safety, land availability).",
        actionPrompt: "Examine the weighted contributions and sensitivity of each planning metric.",
        actionLabel: "Inspect Assumptions",
        targetWindow: "analysis",
        auxWindows: ["results"],
        relevantLayers: ["flood", "landuse"]
      },
      {
        id: "assumptions",
        label: "Assumptions & Constraints",
        shortLabel: "Assumptions",
        description:
          "Audit dataset versions, weighting assumptions, travel speeds, and regulatory rules.",
        actionPrompt: "Review governing constraints, exclusion thresholds, and algorithm provenance.",
        actionLabel: "Inspect Spatial Impact",
        targetWindow: "ai",
        auxWindows: ["trace"],
        relevantLayers: ["parcels", "population"]
      },
      {
        id: "population",
        label: "Affected Population & Equity",
        shortLabel: "Population",
        description:
          "Identify beneficiary wards, population within 15-min isochrone, and underserved pockets.",
        actionPrompt: "Verify spatial equity and population coverage distribution.",
        actionLabel: "Finalize Decision",
        targetWindow: "results",
        auxWindows: ["inspector", "city"],
        relevantLayers: ["population", "facilities"]
      },
      {
        id: "reasons",
        label: "Decision Rationale & Trade-offs",
        shortLabel: "Rationale",
        description:
          "Review plain-language summary of why this option was chosen and its known trade-offs.",
        actionPrompt: "Decision record complete. Ready to commit to active scenario or stress-test.",
        actionLabel: "Apply to Scenario",
        targetWindow: "changes",
        auxWindows: ["scenario"],
        relevantLayers: ["proposals", "facilities"]
      }
    ]
  }
};

export function getWorkflow(id: WorkflowId): WorkflowDef {
  return WORKFLOWS[id] ?? WORKFLOWS.plan;
}
