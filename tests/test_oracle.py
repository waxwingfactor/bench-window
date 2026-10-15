"""Independent exhaustive acceptance checks for tiny scheduling problems.

The oracle enumerates integer start assignments directly from the public input
contract.  It does not call the solver or checker when deciding feasibility.
"""

import copy
import itertools
import random
import unittest

from bench_window.checker import check_schedule
from bench_window.model import validate_plan
from bench_window.solver import solve


def _plan(tasks, *, horizon=10, resources=("bench",), links=(), not_before=0):
    return {
        "schema": 1,
        "title": "Independent acceptance example",
        "horizon": horizon,
        "not_before": not_before,
        "resources": list(resources),
        "tasks": tasks,
        "links": list(links),
    }


def _task(task_id, duration=1, resources=("bench",), **kwargs):
    return {"id": task_id, "duration": duration, "resources": list(resources), **kwargs}


def _assignment_errors(raw, starts):
    """Evaluate a complete assignment without either production checker."""
    tasks = {task["id"]: task for task in raw["tasks"]}
    errors = []
    if set(starts) != set(tasks):
        return ["assignment does not contain exactly the declared tasks"]
    for task_id, task in tasks.items():
        start = starts[task_id]
        if isinstance(start, bool) or not isinstance(start, int):
            errors.append(f"{task_id}: non-integer start")
            continue
        end = start + task["duration"]
        if start < max(0, task.get("release", 0)):
            errors.append(f"{task_id}: starts before release")
        if end > min(raw["horizon"], task.get("deadline", raw["horizon"])):
            errors.append(f"{task_id}: ends after deadline or horizon")
        if "fixed_start" in task:
            if start != task["fixed_start"]:
                errors.append(f"{task_id}: fixed start changed")
        elif start < raw.get("not_before", 0):
            errors.append(f"{task_id}: unfixed task starts before not_before")
    if errors:
        return errors
    for first, second in itertools.combinations(raw["tasks"], 2):
        if set(first["resources"]).intersection(second["resources"]):
            a, b = starts[first["id"]], starts[second["id"]]
            if a < b + second["duration"] and b < a + first["duration"]:
                errors.append(f"{first['id']}/{second['id']}: resource overlap")
    for link in raw.get("links", []):
        before = tasks[link["before"]]
        gap = starts[link["after"]] - starts[before["id"]] - before["duration"]
        if gap < link.get("min_gap", 0):
            errors.append("minimum gap not met")
        if "max_gap" in link and gap > link["max_gap"]:
            errors.append("maximum gap not met")
    return errors


def _exhaustive_schedule(raw):
    """Return the first valid integer assignment, or None after enumeration."""
    domains = []
    task_ids = []
    for task in raw["tasks"]:
        task_ids.append(task["id"])
        if "fixed_start" in task:
            domains.append((task["fixed_start"],))
        else:
            lower = max(0, raw.get("not_before", 0), task.get("release", 0))
            upper = min(raw["horizon"], task.get("deadline", raw["horizon"]))
            domains.append(range(lower, upper - task["duration"] + 1))
    for values in itertools.product(*domains):
        starts = dict(zip(task_ids, values))
        if not _assignment_errors(raw, starts):
            return starts
    return None


class OracleAcceptanceTests(unittest.TestCase):
    def assert_matches_oracle(self, raw, expected=None):
        untouched = copy.deepcopy(raw)
        witness = _exhaustive_schedule(raw)
        expected_status = "feasible" if witness is not None else "infeasible"
        if expected is not None:
            self.assertEqual(expected_status, expected, "invalid acceptance fixture")
        normalized = validate_plan(raw)
        normalized_before = copy.deepcopy(normalized)
        actual = solve(normalized, node_limit=200_000)
        self.assertEqual(actual["status"], expected_status, repr(raw))
        self.assertEqual(raw, untouched, "validation or solving mutated the caller's raw input")
        self.assertEqual(normalized, normalized_before, "solver mutated its input plan")
        if expected_status == "feasible":
            self.assertEqual(_assignment_errors(raw, actual["starts"]), [], repr(actual))
            self.assertEqual(check_schedule(normalized, actual), [], repr(actual))
        return actual

    def test_half_open_adjacency_and_true_overlap(self):
        with self.subTest("touching intervals are allowed"):
            self.assert_matches_oracle(_plan([
                _task("first", 2, fixed_start=0),
                _task("second", 2, fixed_start=2),
            ], horizon=4), "feasible")
        with self.subTest("one second of shared-resource overlap is forbidden"):
            self.assert_matches_oracle(_plan([
                _task("first", 3, fixed_start=0),
                _task("second", 2, fixed_start=2),
            ], horizon=4), "infeasible")

    def test_distinct_resources_and_resource_free_tasks_can_overlap(self):
        self.assert_matches_oracle(_plan([
            _task("one", 4, ("bench",), fixed_start=0),
            _task("two", 4, ("scope",), fixed_start=0),
            _task("wait", 4, (), fixed_start=0),
        ], horizon=4, resources=("bench", "scope")), "feasible")

    def test_multiresource_task_must_fit_every_requested_resource(self):
        self.assert_matches_oracle(_plan([
            _task("occupy-bench", 2, ("bench",), fixed_start=0),
            _task("occupy-scope", 2, ("scope",), fixed_start=2),
            _task("both", 2, ("bench", "scope")),
        ], horizon=4, resources=("bench", "scope")), "infeasible")

    def test_exact_gap_is_measured_from_predecessor_end(self):
        result = self.assert_matches_oracle(_plan([
            _task("prepare", 2, fixed_start=1),
            _task("read", 1),
        ], horizon=8, links=[{
            "before": "prepare", "after": "read", "min_gap": 3, "max_gap": 3,
        }]), "feasible")
        self.assertEqual(result["starts"]["read"], 6)

    def test_max_gap_can_make_individually_available_tasks_infeasible(self):
        self.assert_matches_oracle(_plan([
            _task("prepare", 2, deadline=4),
            _task("read", 1, release=6),
        ], horizon=8, links=[{
            "before": "prepare", "after": "read", "max_gap": 1,
        }]), "infeasible")

    def test_release_and_deadline_are_inclusive_start_and_end_bounds(self):
        result = self.assert_matches_oracle(_plan([
            _task("exact-window", 2, release=3, deadline=5),
        ], horizon=6), "feasible")
        self.assertEqual(result["starts"], {"exact-window": 3})

    def test_completed_fixed_task_is_allowed_before_not_before(self):
        result = self.assert_matches_oracle(_plan([
            _task("completed", 2, fixed_start=0),
            _task("new", 1),
        ], horizon=5, not_before=3), "feasible")
        self.assertEqual(result["starts"]["completed"], 0)
        self.assertGreaterEqual(result["starts"]["new"], 3)

    def test_in_progress_fixed_task_keeps_resource_occupied(self):
        result = self.assert_matches_oracle(_plan([
            _task("running", 5, fixed_start=0),
            _task("new", 1),
        ], horizon=6, not_before=3), "feasible")
        self.assertEqual(result["starts"], {"running": 0, "new": 5})

    def test_unfixed_tasks_cannot_be_scheduled_in_the_past(self):
        self.assert_matches_oracle(_plan([
            _task("new", 3),
        ], horizon=5, not_before=3), "infeasible")

    def test_fixed_start_still_obeys_other_constraints(self):
        for task in (
            _task("pin", 2, fixed_start=1, release=2),
            _task("pin", 2, fixed_start=3, deadline=4),
        ):
            with self.subTest(task=task):
                self.assert_matches_oracle(_plan([task], horizon=5), "infeasible")

    def test_positive_duration_precedence_cycle_has_no_schedule(self):
        self.assert_matches_oracle(_plan([
            _task("a", resources=()),
            _task("b", resources=()),
        ], horizon=5, links=[
            {"before": "a", "after": "b"},
            {"before": "b", "after": "a"},
        ]), "infeasible")

    def test_solver_reorders_tasks_instead_of_using_input_order(self):
        result = self.assert_matches_oracle(_plan([
            _task("flexible", 2),
            _task("urgent", 1, deadline=1),
        ], horizon=3), "feasible")
        self.assertEqual(result["starts"], {"flexible": 1, "urgent": 0})

    def test_repeated_solve_is_deterministic(self):
        raw = _plan([_task("a", 2), _task("b", 2), _task("c", 1)], horizon=6)
        plan = validate_plan(raw)
        first = solve(plan)
        self.assertEqual(first, solve(plan))
        self.assertEqual(_assignment_errors(raw, first["starts"]), [])

    def test_small_search_budget_reports_uncertainty(self):
        plan = validate_plan(_plan([
            _task("a", 1), _task("b", 1), _task("c", 1), _task("d", 1),
        ], horizon=6))
        result = solve(plan, node_limit=1)
        self.assertEqual(result["status"], "search_limit")

    def test_checker_rejects_feasible_label_on_an_invalid_assignment(self):
        raw = _plan([_task("a", 2), _task("b", 2)], horizon=4)
        plan = validate_plan(raw)
        genuine = solve(plan)
        for starts in ({"a": 0}, {"a": 0, "b": 1}, {"a": 0, "b": 3},
                       {"a": 0, "b": 2, "undeclared": 0}, {"a": False, "b": 2}):
            with self.subTest(starts=starts):
                modified = copy.deepcopy(genuine)
                modified["starts"] = starts
                self.assertTrue(check_schedule(plan, modified))

    def test_checker_detects_each_semantic_constraint_with_a_valid_envelope(self):
        examples = [
            (_plan([_task("a", 2), _task("b", 2)], horizon=4),
             {"a": 0, "b": 1}, "overlapping exclusive resources"),
            (_plan([_task("a", 2, deadline=3)], horizon=5),
             {"a": 2}, "ends after deadline"),
            (_plan([_task("a", 1, release=2)], horizon=5),
             {"a": 1}, "starts before release"),
            (_plan([_task("a", 1, fixed_start=1)], horizon=5),
             {"a": 2}, "differs from fixed_start"),
            (_plan([_task("a", 1)], horizon=5, not_before=3),
             {"a": 2}, "starts before not_before"),
            (_plan([_task("a", 1, fixed_start=0), _task("b", 1)], horizon=6,
                   links=[{"before": "a", "after": "b", "min_gap": 1, "max_gap": 2}]),
             {"a": 0, "b": 4}, "above maximum"),
            (_plan([_task("a", 1, fixed_start=0), _task("b", 1)], horizon=6,
                   links=[{"before": "a", "after": "b", "min_gap": 2}]),
             {"a": 0, "b": 1}, "below minimum"),
        ]
        for raw, starts, expected_error in examples:
            with self.subTest(expected_error=expected_error):
                plan = validate_plan(raw)
                genuine = solve(plan)
                self.assertEqual(check_schedule(plan, genuine), [])
                modified = copy.deepcopy(genuine)
                modified["starts"] = starts
                errors = check_schedule(plan, modified)
                self.assertIn(expected_error, " ".join(errors))

    def test_four_hundred_seeded_tiny_cases_against_exhaustive_oracle(self):
        rng = random.Random(0xB3AC7)
        feasible = infeasible = 0
        for case in range(400):
            horizon = rng.randint(3, 7)
            tasks = []
            for index in range(rng.randint(1, 5)):
                release = rng.randint(0, horizon - 1)
                task = _task(
                    f"t{index}",
                    rng.randint(1, min(3, horizon)),
                    rng.sample(["bench", "scope"], rng.randint(0, 2)),
                )
                if rng.random() < .65:
                    task["release"] = release
                if rng.random() < .65:
                    task["deadline"] = rng.randint(task.get("release", 0) + 1, horizon)
                if rng.random() < .3:
                    task["fixed_start"] = rng.randint(0, horizon - 1)
                tasks.append(task)
            links = []
            for before, after in itertools.permutations(tasks, 2):
                if rng.random() < .13:
                    minimum = rng.randint(0, 2)
                    link = {"before": before["id"], "after": after["id"]}
                    if rng.random() < .8:
                        link["min_gap"] = minimum
                    if rng.random() < .6:
                        link["max_gap"] = rng.randint(link.get("min_gap", 0), 3)
                    links.append(link)
            raw = _plan(tasks, horizon=horizon, resources=("bench", "scope"),
                        links=links, not_before=rng.randint(0, horizon - 1))
            with self.subTest(case=case, raw=raw):
                result = self.assert_matches_oracle(raw)
                if result["status"] == "feasible":
                    feasible += 1
                else:
                    infeasible += 1
        self.assertGreater(feasible, 25, "oracle sample should exercise valid solutions")
        self.assertGreater(infeasible, 25, "oracle sample should exercise contradictions")

    def test_three_hundred_random_cases_with_nonempty_individual_windows(self):
        """Exclude easy unary contradictions so resource and link interactions matter."""
        rng = random.Random(0x51A07)
        feasible = infeasible = 0
        for case in range(300):
            horizon = rng.randint(4, 7)
            not_before = rng.randint(0, 1)
            tasks = []
            for index in range(rng.randint(2, 5)):
                release = rng.randint(0, 1)
                duration = rng.randint(1, 2)
                deadline = rng.randint(max(release, not_before) + duration, horizon)
                task = _task(f"t{index}", duration,
                             rng.sample(["bench", "scope"], rng.randint(1, 2)),
                             release=release, deadline=deadline)
                if rng.random() < .2:
                    task["fixed_start"] = rng.randint(release, deadline - duration)
                tasks.append(task)
            links = []
            for before, after in itertools.combinations(tasks, 2):
                if rng.random() < .25:
                    if rng.random() < .5:
                        before, after = after, before
                    minimum = rng.randint(0, 1)
                    link = {"before": before["id"], "after": after["id"],
                            "min_gap": minimum}
                    if rng.random() < .6:
                        link["max_gap"] = rng.randint(minimum, 2)
                    links.append(link)
            raw = _plan(tasks, horizon=horizon, resources=("bench", "scope"),
                        links=links, not_before=not_before)
            with self.subTest(case=case, raw=raw):
                result = self.assert_matches_oracle(raw)
                if result["status"] == "feasible":
                    feasible += 1
                else:
                    infeasible += 1
        self.assertGreater(feasible, 25, "interaction sample should include valid schedules")
        self.assertGreater(infeasible, 25, "interaction sample should include conflicts")


if __name__ == "__main__":
    unittest.main()
