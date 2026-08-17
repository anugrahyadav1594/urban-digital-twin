from typing import Callable, Any, Dict
from pydantic import BaseModel

from app.agents.tools.get_population import get_population
from app.agents.tools.calculate_travel_time import calculate_travel_time
from app.agents.tools.check_constraints import check_constraints
from app.agents.tools.estimate_cost import estimate_cost
from app.agents.tools.calculate_site_score import calculate_site_score

from app.agents.tools.contracts import (
    PopulationRequest,
    TravelTimeRequest,
    CheckConstraintsRequest,
    EstimateCostRequest,
    CalculateSiteScoreRequest,
)

# Registry dictionary mapping tool name to tuple (callable_tool_function, input_schema)
TOOL_REGISTRY: Dict[str, tuple[Callable[[Any], Any], type[BaseModel]]] = {
    "get_population": (get_population, PopulationRequest),
    "calculate_travel_time": (calculate_travel_time, TravelTimeRequest),
    "check_constraints": (check_constraints, CheckConstraintsRequest),
    "estimate_cost": (estimate_cost, EstimateCostRequest),
    "calculate_site_score": (calculate_site_score, CalculateSiteScoreRequest),
}


def invoke_tool(name: str, args: dict) -> BaseModel:
    """Invoke a tool by name with raw dictionary arguments, validating them with the input schema."""
    if name not in TOOL_REGISTRY:
        raise ValueError(f"Tool '{name}' is not registered.")
    
    tool_func, schema = TOOL_REGISTRY[name]
    validated_args = schema.model_validate(args)
    return tool_func(validated_args)
