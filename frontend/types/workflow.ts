export type WorkflowId = "plan" | "stress" | "improve" | "compare" | "explain";

export type WorkflowStatus = "active" | "complete" | "failed" | "cancelled";

export type StepStatus = "locked" | "ready" | "running" | "complete" | "failed";

export type NextAction = {
  id: string;
  label: string;
  available?: boolean;
  reason?: string | null;
  target_step?: string | null;
  target_window?: string | null;
};

export type WorkflowSession = {
  session_id: string;
  workflow_id: WorkflowId;
  scenario_id?: string | null;
  current_step: string;
  completed_steps: string[];
  status: WorkflowStatus;
  context: Record<string, any>;
  result_ids: string[];
  validation_status: string;
  created_at: string;
  updated_at: string;
};

export type WorkflowStepResult = {
  session_id: string;
  workflow_id: WorkflowId;
  step_id: string;
  status: StepStatus;
  result_id?: string | null;
  data: Record<string, any>;
  next_actions: NextAction[];
  provenance: Record<string, any>;
};

export type ConstraintValidationResult = {
  candidate_id: string;
  status: "PASS" | "FAIL";
  constraints: Record<string, string>;
  failed_rules: string[];
  warnings: string[];
  assumptions: string[];
  validation_result_id: string;
};

export type DecisionRecord = {
  recommendation: string;
  overall_score?: number | null;
  score_breakdown: Record<string, number>;
  assumptions: string[];
  constraints: Record<string, string>;
  affected_population: number;
  benefits: string[];
  risks: string[];
  tradeoffs: string[];
  limitations: string[];
  provenance: Record<string, any>;
  source_result_ids: string[];
  scenario_id?: string | null;
};

export type StartWorkflowRequest = {
  workflow_id: WorkflowId;
  scenario_id?: string | number | null;
  initial_context?: Record<string, any>;
};

export type PlanCandidatesRequest = {
  session_id: string;
  facility?: string;
  capacity?: number;
  min_area?: number;
  max_travel_min?: number;
  flood_rule?: string;
  weights?: Record<string, number>;
  max_slope?: number | null;
  allowed_zoning?: string[];
  min_distance_same_type?: number | null;
  service_radius?: number;
};

export type PlanValidateRequest = {
  session_id: string;
  candidate_id: string;
  max_slope?: number | null;
  flood_rule?: string;
  allowed_zoning?: string[];
};

export type PlanCommitRequest = {
  session_id: string;
  candidate_id: string;
  proposal_type?: string;
  label?: string | null;
};

export type StressSimulateRequest = {
  session_id: string;
  hazard_type?: string;
  lon: number;
  lat: number;
  radius_m?: number | null;
  intensity?: number;
  measures?: string[];
};

export type StressRerouteRequest = {
  session_id: string;
  responder_type?: string;
  target_min?: number;
};

export type StressMitigateRequest = {
  session_id: string;
  measures?: string[];
};

export type ImproveGapRequest = {
  session_id: string;
  target_ward?: string | null;
};

export type ImprovePackageRequest = {
  session_id: string;
  num_facilities?: number;
  facility_type?: string;
  objective?: string;
};

export type CompareEvaluateRequest = {
  session_id: string;
  scenario_ids: Array<string | number>;
  facility_type?: string;
};

export type CompareSelectRequest = {
  session_id: string;
  selected_scenario_id: string | number;
};

export type ExplainDecisionRequest = {
  session_id?: string | null;
  result_id?: string | null;
  scenario_id?: string | number | null;
};

export type ApiErrorDetail = {
  code?: string;
  message: string;
  step?: string;
  details?: any[];
};
