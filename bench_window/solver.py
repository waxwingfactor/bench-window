"""Temporal propagation plus complete binary resource-order search.

Each edge (u,v,w,label) means start[v] >= start[u] + w. Node 0 is
anchored at zero. A conflicting exclusive-resource pair must be ordered
in one of two ways in every solution; both branches are searched.
"""

from itertools import combinations

from . import __version__
from .checker import check_schedule
from .model import integer, plan_hash, validate_plan


def _propagate(count, edges):
    distance = [0] * count
    recent = []
    for _ in range(count):
        changed = False
        for u, v, weight, explanation in edges:
            lower = distance[u] + weight
            if distance[v] < lower:
                distance[v] = lower
                changed = True
                recent.append(explanation)
                recent = recent[-8:]
                if v == 0 and lower > 0:
                    return None, recent
        if not changed:
            return distance, []
    return None, recent  # still increasing: a positive constraint cycle


def solve(plan, node_limit=10000):
    """Find one feasible schedule, prove infeasibility, or report search_limit.

    Search order is deterministic. This is feasibility, not makespan optimization.
    The node limit counts propagated constraint networks, including the root.
    """
    plan = validate_plan(plan)
    integer(node_limit, 1, 200000, "node_limit")
    tasks = plan["tasks"]
    index = {t["id"]: i + 1 for i, t in enumerate(tasks)}
    lookup = {t["id"]: t for t in tasks}
    edges = []
    for task in tasks:
        tid = task["id"]
        i = index[tid]
        lower = task["release"]
        if "fixed_start" not in task:
            lower = max(lower, plan["not_before"])
        edges.append((0, i, lower, f"{tid}: release/not_before >= {lower}"))
        upper = task["deadline"] - task["duration"]
        edges.append((i, 0, -upper, f"{tid}: start <= {upper} (end deadline)"))
        if "fixed_start" in task:
            fixed = task["fixed_start"]
            edges.extend([(0, i, fixed, f"{tid}: fixed start >= {fixed}"),
                          (i, 0, -fixed, f"{tid}: fixed start <= {fixed}")])
    for link in plan["links"]:
        a, b = link["before"], link["after"]
        duration = lookup[a]["duration"]
        edges.append((index[a], index[b], duration + link["min_gap"], f"{a} -> {b}: min gap {link['min_gap']}"))
        if "max_gap" in link:
            edges.append((index[b], index[a], -duration - link["max_gap"], f"{a} -> {b}: max gap {link['max_gap']}"))
    pairs = [(a, b) for a, b in combinations(tasks, 2) if set(a["resources"]) & set(b["resources"])]
    stack = [()]
    explored = 0
    last_conflict = []
    result = {"schema": 1, "version": __version__, "plan_sha256": plan_hash(plan)}
    while stack and explored < node_limit:
        choices = stack.pop()
        explored += 1
        distance, conflict = _propagate(len(tasks) + 1, edges + list(choices))
        if distance is None:
            last_conflict = conflict
            continue
        collision = None
        for a, b in pairs:
            sa, sb = distance[index[a["id"]]], distance[index[b["id"]]]
            if sa < sb + b["duration"] and sb < sa + a["duration"]:
                collision = (a, b)
                break
        if collision is None:
            result.update(status="feasible", explored_nodes=explored,
                          starts={tid: distance[i] for tid, i in index.items()})
            errors = check_schedule(plan, result)
            if errors:
                raise RuntimeError("internal schedule check failed: " + "; ".join(errors))
            return result
        a, b = collision
        ia, ib = index[a["id"]], index[b["id"]]
        # LIFO: explore alphabetical a-before-b first, then b-before-a.
        stack.append(choices + ((ib, ia, b["duration"], f"resource order: {b['id']} before {a['id']}"),))
        stack.append(choices + ((ia, ib, a["duration"], f"resource order: {a['id']} before {b['id']}"),))
    result.update(status="search_limit" if stack else "infeasible", explored_nodes=explored)
    result["diagnostic"] = ("Search budget exhausted; feasibility is unknown. Increase --node-limit or simplify the plan."
                            if stack else "No schedule satisfies all declared constraints; the complete resource-order search was exhausted.")
    result["last_conflict"] = last_conflict
    return result
