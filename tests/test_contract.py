"""Strict input, schedule identity, and static export contract checks."""

import copy
import csv
import html
import io
import json
from pathlib import Path
import tempfile
import unittest

from bench_window.checker import check_schedule
from bench_window.model import MAX_BYTES, PlanError, load_plan, plan_hash, read_json, validate_plan
from bench_window.report import run_sheet
from bench_window.solver import solve


def simple_plan():
    return {
        "schema": 1, "title": "Contract example", "horizon": 10,
        "resources": ["bench"],
        "tasks": [
            {"id": "a", "duration": 2, "resources": ["bench"]},
            {"id": "b", "duration": 2, "resources": ["bench"]},
        ],
        "links": [{"before": "a", "after": "b", "min_gap": 0, "max_gap": 4}],
    }


class StrictPlanContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "input.json"

    def assert_invalid(self, raw):
        with self.assertRaises(PlanError):
            validate_plan(raw)

    def test_boolean_is_never_an_integer_parameter(self):
        for value in (True, False):
            for key in ("schema", "horizon", "not_before"):
                raw = simple_plan()
                raw[key] = value
                with self.subTest(key=key, value=value):
                    self.assert_invalid(raw)
            for key in ("duration", "release", "deadline", "fixed_start"):
                raw = simple_plan()
                raw["tasks"][0][key] = value
                with self.subTest(key=key, value=value):
                    self.assert_invalid(raw)
            for key in ("min_gap", "max_gap"):
                raw = simple_plan()
                raw["links"][0][key] = value
                with self.subTest(key=key, value=value):
                    self.assert_invalid(raw)
            with self.assertRaises(PlanError):
                solve(validate_plan(simple_plan()), node_limit=value)

    def test_floats_and_nonfinite_values_are_not_integer_times(self):
        for value in (1.0, float("nan"), float("inf"), -float("inf"), "2", None):
            for key in ("duration", "release", "deadline", "fixed_start"):
                raw = simple_plan()
                raw["tasks"][0][key] = value
                with self.subTest(key=key, value=value):
                    self.assert_invalid(raw)

    def test_json_numeric_constants_are_rejected_before_validation(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value):
                self.path.write_text('{"number": ' + value + '}', encoding="utf-8")
                with self.assertRaises(PlanError):
                    read_json(self.path)

    def test_duplicate_json_keys_are_rejected_at_every_depth(self):
        for text in ('{"title":"one","title":"two"}',
                     '{"tasks":[{"id":"a","id":"b"}]}',
                     '{"starts":{"a":0,"a":1}}'):
            with self.subTest(text=text):
                self.path.write_text(text, encoding="utf-8")
                with self.assertRaisesRegex(PlanError, "duplicate JSON key"):
                    read_json(self.path)

    def test_invalid_json_utf8_and_deep_nesting_fail_clearly(self):
        for payload in (b"{", b'{"a": 1,}', b"\xff\xfe", b"null trailing",
                        b"[" * 2000 + b"0" + b"]" * 2000):
            with self.subTest(payload=payload[:30]):
                self.path.write_bytes(payload)
                with self.assertRaises(PlanError):
                    load_plan(self.path)

    def test_utf8_bom_is_supported(self):
        self.path.write_bytes(b"\xef\xbb\xbf" + json.dumps(simple_plan()).encode("utf-8"))
        self.assertEqual(load_plan(self.path), validate_plan(simple_plan()))

    def test_oversized_json_is_bounded_before_parsing(self):
        self.path.write_bytes(b" " * (MAX_BYTES + 1))
        with self.assertRaisesRegex(PlanError, "exceeds"):
            read_json(self.path)

    def test_unknown_and_missing_keys_are_never_silently_ignored(self):
        for location, typo in (("plan", "horizonn"), ("task", "duraton"), ("link", "maxgap")):
            raw = simple_plan()
            target = raw if location == "plan" else raw["tasks" if location == "task" else "links"][0]
            target[typo] = 1
            with self.subTest(location=location):
                self.assert_invalid(raw)
        for key in ("schema", "title", "horizon", "resources", "tasks"):
            raw = simple_plan()
            del raw[key]
            with self.subTest(missing=key):
                self.assert_invalid(raw)

    def test_collection_types_duplicates_and_references(self):
        mutations = [
            lambda p: p.update(tasks=[]),
            lambda p: p.update(tasks={}),
            lambda p: p.update(resources="bench"),
            lambda p: p.update(resources=["bench", "bench"]),
            lambda p: p["tasks"].append(copy.deepcopy(p["tasks"][0])),
            lambda p: p["tasks"][0].update(resources=["absent"]),
            lambda p: p["tasks"][0].update(resources=["bench", "bench"]),
            lambda p: p["links"].append(copy.deepcopy(p["links"][0])),
            lambda p: p["links"][0].update(before="absent"),
            lambda p: p["links"][0].update(after="a"),
            lambda p: p.update(links={}),
        ]
        for index, mutate in enumerate(mutations):
            raw = simple_plan()
            mutate(raw)
            with self.subTest(index=index):
                self.assert_invalid(raw)

    def test_explicit_resource_and_problem_size_boundaries(self):
        raw = simple_plan()
        raw["horizon"] = 604800
        raw["resources"] = [f"r{i}" for i in range(40)]
        raw["tasks"] = [{"id": f"t{i}", "duration": 1, "resources": [f"r{i}"]}
                        for i in range(40)]
        raw["links"] = []
        self.assertEqual(len(validate_plan(raw)["tasks"]), 40)
        for field, value in (("horizon", 604801), ("resources", raw["resources"] + ["extra"]),
                             ("tasks", raw["tasks"] + [{"id": "extra", "duration": 1, "resources": []}]),
                             ("links", [{"before": "t0", "after": "t1"}] * 401)):
            modified = copy.deepcopy(raw)
            modified[field] = value
            with self.subTest(field=field):
                self.assert_invalid(modified)
        for limit in (0, -1, 200001, 1.5):
            with self.subTest(node_limit=limit), self.assertRaises(PlanError):
                solve(validate_plan(simple_plan()), node_limit=limit)

    def test_ids_are_bounded_ascii_tokens(self):
        for bad in ("", "9task", "_task", "task space", "a/b", "a\\b", "á", "a\n", "a" * 65, None):
            raw = simple_plan()
            raw["tasks"][0]["id"] = bad
            with self.subTest(identifier=bad):
                self.assert_invalid(raw)
        raw = simple_plan()
        raw["tasks"][0]["id"] = "A" + "a" * 63
        raw["links"] = []
        self.assertEqual(validate_plan(raw)["tasks"][0]["id"], "A" + "a" * 63)

    def test_labels_reject_controls_blanks_and_oversized_text(self):
        for bad in ("", "   ", "a\nb", "a\tb", "a\x00b", "a\u202eb", "a\ud800b", "x" * 161, None):
            for field in ("title", "label"):
                raw = simple_plan()
                if field == "title":
                    raw[field] = bad
                else:
                    raw["tasks"][0][field] = bad
                with self.subTest(field=field, value=repr(bad)):
                    self.assert_invalid(raw)
        raw = simple_plan()
        raw["title"] = "測定 — α & β " + "x" * 140
        self.assertEqual(validate_plan(raw)["title"], raw["title"])

    def test_time_bounds_and_gap_direction_are_strict(self):
        for key, bad in (("duration", 0), ("duration", 11), ("release", -1),
                         ("deadline", 11), ("fixed_start", -1)):
            raw = simple_plan()
            raw["tasks"][0][key] = bad
            with self.subTest(key=key, value=bad):
                self.assert_invalid(raw)
        for key, bad in (("min_gap", -1), ("min_gap", 11), ("max_gap", -1)):
            raw = simple_plan()
            raw["links"][0][key] = bad
            with self.subTest(key=key, value=bad):
                self.assert_invalid(raw)
        raw = simple_plan()
        raw["links"][0].update(min_gap=3, max_gap=2)
        self.assert_invalid(raw)


class ScheduleAndExportContractTests(unittest.TestCase):
    def test_normalized_identity_ignores_declaration_order_and_explicit_defaults(self):
        raw = simple_plan()
        equivalent = copy.deepcopy(raw)
        equivalent["tasks"].reverse()
        equivalent["resources"].reverse()
        equivalent["not_before"] = 0
        for task in equivalent["tasks"]:
            task.update(label=task["id"], release=0, deadline=10)
        self.assertEqual(plan_hash(validate_plan(raw)), plan_hash(validate_plan(equivalent)))
        self.assertEqual(len(plan_hash(validate_plan(raw))), 64)

    def test_changed_plan_identity_rejects_an_otherwise_valid_schedule(self):
        plan = validate_plan(simple_plan())
        result = solve(plan)
        changed = copy.deepcopy(plan)
        changed["title"] = "A distinct declared plan"
        errors = check_schedule(changed, result)
        self.assertTrue(errors)
        self.assertIn("plan_sha256", " ".join(errors))

    def test_schedule_contract_rejects_unknown_missing_or_malformed_fields(self):
        plan = validate_plan(simple_plan())
        original = solve(plan)
        variants = []
        for field, value in (("schema", True), ("version", "future"), ("status", "infeasible"),
                             ("plan_sha256", "0" * 64), ("explored_nodes", True),
                             ("starts", {"a": 0, "b": False}), ("starts", {"a": 0}),
                             ("starts", {"a": 0, "b": 2, "extra": 4})):
            result = copy.deepcopy(original)
            result[field] = value
            variants.append(result)
        unknown = copy.deepcopy(original)
        unknown["unrecognized"] = 1
        variants.append(unknown)
        missing = copy.deepcopy(original)
        del missing["starts"]
        variants.append(missing)
        for index, result in enumerate(variants):
            with self.subTest(index=index):
                self.assertTrue(check_schedule(plan, result))

    def test_html_escapes_hostile_text_and_preserves_literal_template_words(self):
        raw = simple_plan()
        raw["title"] = 'TITLE ROWS HASH $title ${rows} <img src=x onerror="alert(1)"> & Ω'
        raw["tasks"][0]["label"] = '<script>alert("x")</script> TITLE ROWS HASH $hash'
        plan = validate_plan(raw)
        result = solve(plan)
        _, markup = run_sheet(plan, result)
        self.assertIn(html.escape(raw["title"]), markup)
        self.assertIn(html.escape(raw["tasks"][0]["label"]), markup)
        self.assertNotIn("<script>", markup)
        self.assertNotIn("<img src=x", markup)
        self.assertIn(result["plan_sha256"], markup)
        self.assertIn("Content-Security-Policy", markup)
        self.assertIn("default-src 'none'", markup)

    def test_csv_neutralizes_formula_prefixes_including_leading_spaces(self):
        labels = ['=HYPERLINK("https://example.invalid")', "+1+2", "-1+2", "@SUM(1)",
                  "  =2+2", "Normal, quoted \"label\" & Ω", "TITLE ROWS HASH"]
        raw = simple_plan()
        raw["tasks"] = [{"id": f"t{i}", "label": value, "duration": 1, "resources": []}
                        for i, value in enumerate(labels)]
        raw["links"] = []
        plan = validate_plan(raw)
        csv_text, _ = run_sheet(plan, solve(plan))
        rows = list(csv.DictReader(io.StringIO(csv_text)))
        self.assertEqual(len(rows), len(labels))
        by_id = {row["task"]: row for row in rows}
        for index, label in enumerate(labels):
            expected = "'" + label if index < 5 else label
            self.assertEqual(by_id[f"t{index}"]["label"], expected)


if __name__ == "__main__":
    unittest.main()
