"""Real subprocess acceptance checks; each invocation has fresh temporary outputs.

These development tests run ``python -m`` from the source root. Published wheel
and source-distribution installation is verified separately outside the checkout.
"""

import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CommandLineAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bench-window-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def cli(self, *args, expected=0):
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        result = subprocess.run([sys.executable, "-m", "bench_window", *map(str, args)],
                                cwd=ROOT, env=env, text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, expected,
                         f"command {args!r}\nstdout: {result.stdout}\nstderr: {result.stderr}")
        self.assertNotIn("Traceback", result.stderr)
        return result

    def write_plan(self, name="plan.json"):
        path = self.base / name
        plan = {
            "schema": 1, "title": "CLI test", "horizon": 4, "resources": ["bench"],
            "tasks": [{"id": "a", "duration": 2, "resources": ["bench"]},
                      {"id": "b", "duration": 2, "resources": ["bench"]}],
            "links": [],
        }
        path.write_text(json.dumps(plan), encoding="utf-8")
        return path

    def test_help_and_version(self):
        self.assertIn("solve", self.cli("--help").stdout)
        self.assertEqual(self.cli("--version").stdout.strip(), "1.0.0")

    def test_packaged_mixed_and_pinned_examples_complete_full_workflow(self):
        for name in ("mixed-run", "pinned-run"):
            with self.subTest(name=name):
                plan = self.base / f"{name}.json"
                self.cli("example", "--name", name, "--out", plan)
                raw = json.loads(plan.read_text(encoding="utf-8"))
                self.assertEqual(raw["schema"], 1)
                self.assertGreater(len(raw["tasks"]), 2)
                output = self.base / f"{name}-solved"
                solved = self.cli("solve", plan, "--out", output)
                self.assertEqual(json.loads(solved.stdout)["status"], "feasible")
                self.assertEqual({p.name for p in output.iterdir()},
                                 {"result.json", "schedule.csv", "run-sheet.html"})
                checked = self.cli("check", plan, output / "result.json")
                self.assertEqual(json.loads(checked.stdout), {"valid": True, "errors": []})
                report = self.base / f"{name}-report"
                self.cli("report", plan, output / "result.json", "--out", report)
                self.assertEqual({p.name for p in report.iterdir()}, {"schedule.csv", "run-sheet.html"})
                self.assertEqual((report / "schedule.csv").read_bytes(), (output / "schedule.csv").read_bytes())
                self.assertEqual((report / "run-sheet.html").read_bytes(), (output / "run-sheet.html").read_bytes())
                rows = list(csv.DictReader(io.StringIO((report / "schedule.csv").read_text(encoding="utf-8"))))
                self.assertEqual({r["task"] for r in rows}, {t["id"] for t in raw["tasks"]})

    def test_impossible_example_emits_result_only_and_exit_three(self):
        plan = self.base / "impossible.json"
        self.cli("example", "--name", "impossible", "--out", plan)
        output = self.base / "impossible"
        completed = self.cli("solve", plan, "--out", output, expected=3)
        self.assertEqual(json.loads(completed.stdout)["status"], "infeasible")
        self.assertEqual({p.name for p in output.iterdir()}, {"result.json"})
        result = json.loads((output / "result.json").read_text(encoding="utf-8"))
        self.assertNotIn("starts", result)
        self.assertIn("diagnostic", result)

    def test_search_limit_emits_result_only_and_exit_four(self):
        plan = self.write_plan()
        output = self.base / "limited"
        completed = self.cli("solve", plan, "--out", output, "--node-limit", 1, expected=4)
        self.assertEqual(json.loads(completed.stdout)["status"], "search_limit")
        self.assertEqual({p.name for p in output.iterdir()}, {"result.json"})
        result = json.loads((output / "result.json").read_text(encoding="utf-8"))
        self.assertNotIn("starts", result)
        self.assertEqual(result["explored_nodes"], 1)

    def test_modified_candidate_is_invalid_and_cannot_produce_report(self):
        plan = self.write_plan()
        output = self.base / "solved"
        self.cli("solve", plan, "--out", output)
        result_path = output / "result.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["starts"] = {"a": 0, "b": 1}
        result_path.write_text(json.dumps(result), encoding="utf-8")
        checked = self.cli("check", plan, result_path, expected=5)
        self.assertFalse(json.loads(checked.stdout)["valid"])
        self.assertIn("overlapping", " ".join(json.loads(checked.stdout)["errors"]))
        report = self.base / "forbidden-report"
        self.cli("report", plan, result_path, "--out", report, expected=5)
        self.assertFalse(report.exists())

    def test_stale_plan_hash_fails_check_and_report(self):
        plan = self.write_plan()
        output = self.base / "solved"
        self.cli("solve", plan, "--out", output)
        raw = json.loads(plan.read_text(encoding="utf-8"))
        raw["title"] = "Changed after solving"
        plan.write_text(json.dumps(raw), encoding="utf-8")
        checked = self.cli("check", plan, output / "result.json", expected=5)
        self.assertIn("plan_sha256", " ".join(json.loads(checked.stdout)["errors"]))
        report = self.base / "stale-report"
        self.cli("report", plan, output / "result.json", "--out", report, expected=5)
        self.assertFalse(report.exists())

    def test_solve_refuses_existing_empty_directory_and_preserves_existing_files(self):
        plan = self.write_plan()
        for name, occupied in (("empty", False), ("occupied", True)):
            with self.subTest(name=name):
                output = self.base / name
                output.mkdir()
                if occupied:
                    (output / "result.json").write_text("sentinel", encoding="utf-8")
                self.cli("solve", plan, "--out", output, expected=2)
                self.assertEqual({p.name for p in output.iterdir()}, {"result.json"} if occupied else set())
                if occupied:
                    self.assertEqual((output / "result.json").read_text(encoding="utf-8"), "sentinel")

    def test_example_refuses_existing_file_or_directory(self):
        target = self.base / "exists.json"
        target.write_text("sentinel", encoding="utf-8")
        self.cli("example", "--name", "mixed-run", "--out", target, expected=2)
        self.assertEqual(target.read_text(encoding="utf-8"), "sentinel")
        directory = self.base / "empty"
        directory.mkdir()
        self.cli("example", "--out", directory, expected=2)
        self.assertEqual(list(directory.iterdir()), [])

    def test_report_refuses_existing_empty_directory(self):
        plan = self.write_plan()
        output = self.base / "solved"
        self.cli("solve", plan, "--out", output)
        existing = self.base / "report"
        existing.mkdir()
        self.cli("report", plan, output / "result.json", "--out", existing, expected=2)
        self.assertEqual(list(existing.iterdir()), [])

    def test_invalid_inputs_fail_without_creating_output(self):
        for index, payload in enumerate((b"{", b"\xff", b'{"schema":1,"schema":1}', b"NaN")):
            plan = self.base / f"bad-{index}.json"
            plan.write_bytes(payload)
            output = self.base / f"bad-{index}-output"
            self.cli("solve", plan, "--out", output, expected=2)
            self.assertFalse(output.exists())
        missing = self.base / "does-not-exist.json"
        self.cli("solve", missing, "--out", self.base / "missing-output", expected=2)
        self.assertFalse((self.base / "missing-output").exists())

    def test_invalid_node_limit_fails_without_output(self):
        plan = self.write_plan()
        for value in ("0", "-1", "200001", "not-a-number"):
            output = self.base / ("limit-" + value)
            self.cli("solve", plan, "--out", output, "--node-limit", value, expected=2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
