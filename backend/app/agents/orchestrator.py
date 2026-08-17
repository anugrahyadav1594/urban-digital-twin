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
        # 1. Extract Planning Intent
        intent = self.planning_agent.plan(user_request)
        
        # Fallback values if LLM leaves fields empty
        location = intent.location or "downtown"
        facility_type = intent.facility_type or "facility"
        constraints = intent.constraints or []
        
        # 2. Invoke Deterministic Tools
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
        
        # 3. Call Specialized Logical Agents to Interpret Deterministic Outputs
        gis_interpretation = self.gis_agent.interpret(
            location=location,
            population=pop_res.population,
            density=pop_res.density_per_sqkm,
            travel_time=travel_res.travel_time_minutes,
            distance=travel_res.distance_km
        )
        
        cost_interpretation = self.cost_agent.interpret(
            facility_type=facility_type,
            scale="medium",
            estimated_cost=cost_res.estimated_cost_usd,
            confidence=cost_res.confidence
        )
        
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
        validation = self.critic_agent.validate(deterministic_data, interpretations)
        
        # 5. Synthesize final markdown report
        report = self.report_agent.generate_report(
            user_request=user_request,
            deterministic_data=deterministic_data,
            interpretations=interpretations,
            validation_status=validation
        )
        
        return {
            "intent": intent.model_dump(),
            "deterministic_metrics": deterministic_data,
            "interpretations": interpretations,
            "validation": validation,
            "report": report
        }
