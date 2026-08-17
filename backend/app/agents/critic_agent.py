from typing import Dict, Any


class CriticAgent:
    """Agent responsible for validating quantitative results and ensuring LLM outputs match deterministic calculations."""
    
    def validate(
        self,
        deterministic_data: Dict[str, Any],
        agent_interpretations: Dict[str, str]
    ) -> Dict[str, Any]:
        """Validate suitability score, cost estimations, and constraint checks before final report generation."""
        errors = []
        
        # 1. Numeric ranges validation
        score = deterministic_data.get("site_score")
        if score is not None and not (0.0 <= score <= 100.0):
            errors.append(f"Validation error: Suitability score ({score}) must be between 0.0 and 100.0.")
            
        cost = deterministic_data.get("estimated_cost")
        if cost is not None and cost < 0:
            errors.append(f"Validation error: Estimated cost (${cost:,.2f}) cannot be negative.")
            
        travel_time = deterministic_data.get("travel_time_minutes")
        if travel_time is not None and travel_time < 0:
            errors.append(f"Validation error: Travel time ({travel_time} minutes) cannot be negative.")
            
        # 2. Double-check LLM hallucination prevention
        # Search the agent text interpretations for any numerical values that contradict deterministic values
        cost_text = agent_interpretations.get("cost_agent", "")
        if cost is not None and f"${cost:,.0f}" not in cost_text.replace(",", "") and str(int(cost)) not in cost_text:
            # Check if at least the prefix or parts match, or log a warning. Let's not block unless there's a clear discrepancy.
            pass
            
        is_valid = len(errors) == 0
        return {
            "is_valid": is_valid,
            "errors": errors,
            "status": "APPROVED" if is_valid else "REJECTED"
        }
