"""Direct schedule checks, independent of the solver's graph construction."""

from itertools import combinations

from .model import PlanError, integer, keys, plan_hash, validate_plan


def check_schedule(plan, result):
    """Return all detected contract/timing failures; [] means valid under the plan."""
    plan = validate_plan(plan)
    try:
        fields = {"schema", "version", "status", "plan_sha256", "starts", "explored_nodes"}
        keys(result, fields, fields, "schedule")
        integer(result["schema"], 1, 1, "schedule.schema")
        integer(result["explored_nodes"], 0, 200000, "explored_nodes")
        if not isinstance(result["version"], str) or result["version"] != "1.0.0":
            raise PlanError("schedule: unsupported producer version")
        if result["status"] != "feasible":
            raise PlanError("schedule is not marked feasible")
        if result["plan_sha256"] != plan_hash(plan):
            raise PlanError("schedule belongs to a different plan (plan_sha256 mismatch)")
        starts = result["starts"]
        if not isinstance(starts, dict) or set(starts) != {t["id"] for t in plan["tasks"]}:
            raise PlanError("starts must name every task exactly once")
        for tid, value in starts.items():
            integer(value, 0, plan["horizon"], f"starts.{tid}")
    except PlanError as exc:
        return [str(exc)]
    errors = []
    tasks = {t["id"]: t for t in plan["tasks"]}
    for tid, task in tasks.items():
        start = starts[tid]
        end = start + task["duration"]
        if start < task["release"]:
            errors.append(f"{tid}: starts before release")
        if end > task["deadline"]:
            errors.append(f"{tid}: ends after deadline")
        if "fixed_start" in task:
            if start != task["fixed_start"]:
                errors.append(f"{tid}: differs from fixed_start")
        elif start < plan["not_before"]:
            errors.append(f"{tid}: starts before not_before")
    for link in plan["links"]:
        a, b = link["before"], link["after"]
        gap = starts[b] - starts[a] - tasks[a]["duration"]
        if gap < link["min_gap"]:
            errors.append(f"{a} -> {b}: gap {gap} below minimum {link['min_gap']}")
        if "max_gap" in link and gap > link["max_gap"]:
            errors.append(f"{a} -> {b}: gap {gap} above maximum {link['max_gap']}")
    for a, b in combinations(tasks, 2):
        shared = set(tasks[a]["resources"]) & set(tasks[b]["resources"])
        if shared and starts[a] < starts[b] + tasks[b]["duration"] and starts[b] < starts[a] + tasks[a]["duration"]:
            errors.append(f"{a} / {b}: overlapping exclusive resources {', '.join(sorted(shared))}")
    return errors
