from typing import Dict, Any

from app.agents.llm_client import LLMClient
from app.agents.planning_agent import PlanningAgent
from app.agents.gis_agent import GISAgent
from app.agents.cost_agent import CostAgent
from app.agents.risk_agent import RiskAgent
from app.agents.critic_agent import CriticAgent
from app.agents.report_agent import ReportAgent
from app.agents.tools import invoke_tool


class Orchestrator:
    """Core orchestrator coordinating the entire AI planning workflow."""
    
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()
        self.planning_agent = PlanningAgent(self.llm_client)
        self.gis_agent = GISAgent(self.llm_client)
        self.cost_agent = CostAgent(self.llm_client)
        self.risk_agent = RiskAgent(self.llm_client)
        self.critic_agent = CriticAgent()
        self.report_agent = ReportAgent(self.llm_client)
        
    def execute(self, user_request: str) -> Dict[str, Any]:
        """Execute the complete vertical planning orchestration flow."""
        print("[Orchestrator] Starting planning flow...")
        
        # 1. Extract Planning Intent
        print("[Orchestrator] Step 1: Extracting planning intent using PlanningAgent...")
        intent = self.planning_agent.plan(user_request)
        print(f"[Orchestrator] Intent parsed: {intent.model_dump()}")
        
        # Fallback values if LLM leaves fields empty
        location = intent.location or "downtown"
        facility_type = intent.facility_type or "facility"
        constraints = intent.constraints or []
        
        # 2. Invoke Deterministic Tools
        print("[Orchestrator] Step 2: Querying deterministic tools for spatial metrics...")
        # Demographic metrics
        pop_res = invoke_tool("get_population", {"location": location})
        
        # Spatial metrics
        travel_res = invoke_tool(
            "calculate_travel_time", 
            {"origin": location, "destination": "central hub", "mode": "driving"}
        )
        
        # Environmental and constraint checks
        constraint_res = invoke_tool(
            "check_constraints", 
            {"location": location, "constraints": constraints}
        )
        
        # Cost estimate
        cost_res = invoke_tool(
            "estimate_cost", 
            {"facility_type": facility_type, "scale": "medium"}
        )
        
        # Site suitability scoring
        score_res = invoke_tool(
            "calculate_site_score", 
            {"location": location, "facility_type": facility_type}
        )
        
        # Combine all deterministic data
        deterministic_data = {
            "location": location,
            "facility_type": facility_type,
            "population": pop_res.population,
            "density": pop_res.density_per_sqkm,
            "travel_time_minutes": travel_res.travel_time_minutes,
            "distance_km": travel_res.distance_km,
            "violations": constraint_res.violations,
            "constraints_passed": constraint_res.passed,
            "estimated_cost": cost_res.estimated_cost_usd,
            "cost_confidence": cost_res.confidence,
            "site_score": score_res.score,
            "site_score_details": score_res.details,
        }
        print(f"[Orchestrator] Deterministic metrics gathered: {deterministic_data}")
        
        # 3. Call Specialized Logical Agents to Interpret Deterministic Outputs
        print("[Orchestrator] Step 3: Invoking specialized logical agents...")
        print("  - Running GISAgent...")
        gis_interpretation = self.gis_agent.interpret(
            location=location,
            population=pop_res.population,
            density=pop_res.density_per_sqkm,
            travel_time=travel_res.travel_time_minutes,
            distance=travel_res.distance_km
        )
        
        print("  - Running CostAgent...")
        cost_interpretation = self.cost_agent.interpret(
            facility_type=facility_type,
            scale="medium",
            estimated_cost=cost_res.estimated_cost_usd,
            confidence=cost_res.confidence
        )
        
        print("  - Running RiskAgent...")
        risk_interpretation = self.risk_agent.interpret(
            location=location,
            constraints=constraints,
            violations=constraint_res.violations,
            passed=constraint_res.passed
        )
        
        interpretations = {
            "gis_agent": gis_interpretation,
            "cost_agent": cost_interpretation,
            "risk_agent": risk_interpretation
        }
        
        # 4. Critic Validation checks
        print("[Orchestrator] Step 4: Validating results with CriticAgent...")
        validation = self.critic_agent.validate(deterministic_data, interpretations)
        print(f"[Orchestrator] Critic validation status: {validation['status']}")
        
        # 5. Synthesize final markdown report
        print("[Orchestrator] Step 5: Synthesizing final report with ReportAgent...")
        report = self.report_agent.generate_report(
            user_request=user_request,
            deterministic_data=deterministic_data,
            interpretations=interpretations,
            validation_status=validation
        )
        print("[Orchestrator] Execution finished successfully.")

        steps = [
            {"id": "s0", "agent": "Planner", "text": "Extracted planning intent", "state": "done", "tool": "decompose_goal", "output": str(intent.model_dump())},
            {"id": "s1", "agent": "GIS", "text": "Ran spatial site score and demographic check", "state": "done", "tool": "calculate_site_score", "output": str(score_res.model_dump())},
            {"id": "s2", "agent": "Network", "text": "Calculated catchment travel time and distance", "state": "done", "tool": "calculate_travel_time", "output": str(travel_res.model_dump())},
            {"id": "s3", "agent": "Risk", "text": "Checked environmental and zoning constraints", "state": "done", "tool": "check_constraints", "output": str(constraint_res.model_dump())},
            {"id": "s4", "agent": "Optimization", "text": "Evaluated site metrics against multi-criteria profile", "state": "done", "tool": "calculate_site_score", "output": str(score_res.score)},
            {"id": "s5", "agent": "Cost", "text": "Estimated capital expenditure", "state": "done", "tool": "estimate_cost", "output": str(cost_res.model_dump())},
            {"id": "s6", "agent": "Validator", "text": "Validated result consistency with CriticAgent", "state": "done", "tool": "validate_result", "output": str(validation["status"])},
        ]
        
        return {
            "intent": intent.model_dump(),
            "deterministic_metrics": deterministic_data,
            "interpretations": interpretations,
            "validation": validation,
            "report": report,
            "steps": steps,
            "result_id": f"res_ai_{location}",
            "comparison": None,
        }
