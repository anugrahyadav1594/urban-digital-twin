"""Infrastructure capacity allocation under a budget. ARCHITECTURE §15."""
from __future__ import annotations

from ortools.sat.python import cp_model

from ..contracts import EngineResult, Provenance
from .problem_spec import AllocationProblem, SolveOptions

ALGORITHM = "optimization.allocation"
ALGORITHM_VERSION = "0.1.0"


def solve_allocation(
    problem: AllocationProblem,
    provenance: Provenance,
    options: SolveOptions | None = None,
) -> EngineResult:
    """Integer knapsack-style allocation maximising total benefit."""
    problem.validate()
    options = options or SolveOptions()
    res = EngineResult(result_type="allocation", provenance=provenance)

    n = len(problem.zone_ids)
    model = cp_model.CpModel()

    ub = []
    for i in range(n):
        cap = int(problem.budget // max(problem.unit_cost[i], 1e-9))
        if problem.max_units is not None:
            cap = min(cap, int(problem.max_units[i]))
        ub.append(max(cap, 0))

    x = [model.NewIntVar(
            int(problem.min_units[i]) if problem.min_units else 0,
            ub[i], f"x_{i}") for i in range(n)]

    model.Add(sum(
        x[i] * int(round(problem.unit_cost[i])) for i in range(n)
    ) <= int(round(problem.budget)))

    model.Maximize(sum(
        x[i] * int(round(problem.benefit[i] * 1000)) for i in range(n)
    ))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = options.time_limit_seconds
    solver.parameters.random_seed = options.seed
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        res.warnings.append("allocation infeasible under the given budget")
        return res

    spent = 0.0
    total_benefit = 0.0
    for i in range(n):
        units = solver.Value(x[i])
        cost = units * problem.unit_cost[i]
        spent += cost
        total_benefit += units * problem.benefit[i]
        res.records.append({
            "zone_id": problem.zone_ids[i],
            "units_allocated": int(units),
            "cost": round(cost, 2),
            "demand": round(float(problem.demand[i]), 2),
            "demand_met_ratio": round(min(1.0, units / problem.demand[i]), 4)
            if problem.demand[i] > 0 else None,
        })

    res.add("budget", round(problem.budget, 2), "currency")
    res.add("budget_spent", round(spent, 2), "currency")
    res.add("budget_remaining", round(problem.budget - spent, 2), "currency")
    res.add("total_benefit", round(total_benefit, 2), "benefit")
    res.add("units_allocated",
            sum(r["units_allocated"] for r in res.records), "count")
    return res
