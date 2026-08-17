"""Facility location optimization. ARCHITECTURE §15.

p-median (minimise population-weighted travel cost) and maximal coverage
(maximise demand within a cost threshold), both via OR-Tools CP-SAT.
"""
from __future__ import annotations

from typing import Any

from ortools.sat.python import cp_model

from ..contracts import EngineResult, Provenance
from .problem_spec import FacilityLocationProblem, SolveOptions

ALGORITHM = "optimization.facility_location"
ALGORITHM_VERSION = "0.1.0"

_SCALE = 1000  # CP-SAT is integral; scale floats to preserve precision.


def _status_name(status: int) -> str:
    return {
        cp_model.OPTIMAL: "optimal",
        cp_model.FEASIBLE: "feasible",
        cp_model.INFEASIBLE: "infeasible",
        cp_model.MODEL_INVALID: "model_invalid",
        cp_model.UNKNOWN: "unknown",
    }.get(status, "unknown")


def solve_facility_location(
    problem: FacilityLocationProblem,
    provenance: Provenance,
    options: SolveOptions | None = None,
) -> EngineResult:
    """p-median: open exactly p sites minimising weighted travel cost."""
    problem.validate()
    options = options or SolveOptions()
    res = EngineResult(result_type="facility_location", provenance=provenance)

    n_d, n_c = len(problem.demand_ids), len(problem.candidate_ids)
    model = cp_model.CpModel()

    open_v = [model.NewBoolVar(f"open_{j}") for j in range(n_c)]
    assign = {}
    for i in range(n_d):
        for j in range(n_c):
            c = problem.cost_matrix[i][j]
            if c is None:
                continue
            if problem.max_cost is not None and c > problem.max_cost:
                continue
            assign[(i, j)] = model.NewBoolVar(f"a_{i}_{j}")

    model.Add(sum(open_v) == problem.p)

    for cid in problem.must_open:
        if cid in problem.candidate_ids:
            model.Add(open_v[list(problem.candidate_ids).index(cid)] == 1)
    for cid in problem.must_close:
        if cid in problem.candidate_ids:
            model.Add(open_v[list(problem.candidate_ids).index(cid)] == 0)

    unserved = []
    for i in range(n_d):
        opts = [assign[(i, j)] for j in range(n_c) if (i, j) in assign]
        if not opts:
            unserved.append(problem.demand_ids[i])
            continue
        model.Add(sum(opts) == 1)
        for j in range(n_c):
            if (i, j) in assign:
                model.Add(assign[(i, j)] <= open_v[j])

    if problem.capacities is not None:
        for j in range(n_c):
            terms = [
                assign[(i, j)] * int(round(problem.demand_weights[i]))
                for i in range(n_d) if (i, j) in assign
            ]
            if terms:
                model.Add(sum(terms) <= int(round(problem.capacities[j])))

    obj = []
    for (i, j), var in assign.items():
        w = problem.demand_weights[i]
        c = problem.cost_matrix[i][j]
        obj.append(var * int(round(w * c)))
    if problem.fixed_costs:
        for j in range(n_c):
            obj.append(open_v[j] * int(round(problem.fixed_costs[j] * _SCALE)))
    model.Minimize(sum(obj) if obj else 0)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = options.time_limit_seconds
    solver.parameters.random_seed = options.seed
    solver.parameters.num_search_workers = options.workers
    status = solver.Solve(model)
    name = _status_name(status)

    res.add("solver_status_code", status, "code")
    res.artifacts.append({"type": "solver", "status": name,
                          "wall_time_s": f"{solver.WallTime():.3f}"})

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        res.warnings.append(f"no solution found (status={name})")
        res.add("sites_opened", 0, "count")
        return res

    selected = [problem.candidate_ids[j] for j in range(n_c)
                if solver.Value(open_v[j]) == 1]
    total_w = sum(problem.demand_weights)
    weighted_cost = 0.0
    served_w = 0.0
    assignments = []
    for (i, j), var in assign.items():
        if solver.Value(var) == 1:
            w = problem.demand_weights[i]
            c = problem.cost_matrix[i][j]
            weighted_cost += w * c
            served_w += w
            assignments.append({
                "demand_id": problem.demand_ids[i],
                "facility_id": problem.candidate_ids[j],
                "cost": round(float(c), 2),
                "weight": round(float(w), 2),
            })

    res.records = [{"selected_sites": selected}] + assignments
    res.add("sites_opened", len(selected), "count")
    res.add("objective_weighted_cost", round(weighted_cost, 2), "weighted_cost")
    res.add("mean_cost_per_demand_unit",
            round(weighted_cost / served_w, 2) if served_w else None, "cost")
    res.add("demand_served", round(served_w, 2), "persons")
    res.add("demand_total", round(total_w, 2), "persons")
    res.add("demand_coverage",
            round(served_w / total_w, 4) if total_w else 0.0, "ratio")
    if unserved:
        res.warnings.append(f"{len(unserved)} demand points unreachable within max_cost")
    return res


def solve_max_coverage(
    problem: FacilityLocationProblem,
    provenance: Provenance,
    options: SolveOptions | None = None,
) -> EngineResult:
    """Maximal covering: open p sites maximising demand within max_cost."""
    problem.validate()
    if problem.max_cost is None:
        raise ValueError("max_coverage requires problem.max_cost")
    options = options or SolveOptions()
    res = EngineResult(result_type="max_coverage", provenance=provenance)

    n_d, n_c = len(problem.demand_ids), len(problem.candidate_ids)
    model = cp_model.CpModel()
    open_v = [model.NewBoolVar(f"open_{j}") for j in range(n_c)]
    cov = [model.NewBoolVar(f"cov_{i}") for i in range(n_d)]

    model.Add(sum(open_v) == problem.p)
    for i in range(n_d):
        eligible = [
            open_v[j] for j in range(n_c)
            if problem.cost_matrix[i][j] is not None
            and problem.cost_matrix[i][j] <= problem.max_cost
        ]
        if eligible:
            model.Add(cov[i] <= sum(eligible))
        else:
            model.Add(cov[i] == 0)

    model.Maximize(sum(
        cov[i] * int(round(problem.demand_weights[i])) for i in range(n_d)
    ))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = options.time_limit_seconds
    solver.parameters.random_seed = options.seed
    status = solver.Solve(model)
    name = _status_name(status)
    res.artifacts.append({"type": "solver", "status": name,
                          "wall_time_s": f"{solver.WallTime():.3f}"})

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        res.warnings.append(f"no solution found (status={name})")
        return res

    selected = [problem.candidate_ids[j] for j in range(n_c)
                if solver.Value(open_v[j]) == 1]
    covered = sum(problem.demand_weights[i] for i in range(n_d)
                  if solver.Value(cov[i]) == 1)
    total = sum(problem.demand_weights)

    res.records = [{
        "selected_sites": selected,
        "covered_demand_ids": [problem.demand_ids[i] for i in range(n_d)
                               if solver.Value(cov[i]) == 1],
    }]
    res.add("sites_opened", len(selected), "count")
    res.add("demand_covered", round(covered, 2), "persons")
    res.add("demand_total", round(total, 2), "persons")
    res.add("coverage_ratio", round(covered / total, 4) if total else 0.0, "ratio")
    res.add("max_cost_threshold", problem.max_cost, "seconds")
    return res
