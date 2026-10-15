"""Command-line workflow with no-clobber output and explicit result codes."""

import argparse
import importlib.resources
import json
from pathlib import Path
import sys

from . import __version__
from .checker import check_schedule
from .model import PlanError, load_plan, read_json
from .report import run_sheet
from .solver import solve


def encode(value):
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_new(path, content):
    """Create one new file exclusively; refuse existing files and symlinks."""
    with Path(path).open("x", encoding="utf-8", newline="") as stream:
        stream.write(content)


def publish(directory, files):
    """Exclusive local output directory; rollback only files created by this call."""
    directory = Path(directory)
    directory.mkdir()  # O_EXCL-like reservation, including empty-directory collisions
    created = []
    try:
        for name, content in files.items():
            path = directory / name
            with path.open("x", encoding="utf-8", newline="") as stream:
                created.append(path)
                stream.write(content)
    except BaseException:
        for path in created:
            try:
                path.unlink()
            except OSError:
                pass
        try:
            directory.rmdir()
        except OSError:
            pass
        raise


def parser():
    p = argparse.ArgumentParser(description="Check whether a small manual lab run fits declared timing and exclusive-resource constraints. Times are integer elapsed seconds.")
    p.add_argument("--version", action="version", version=__version__)
    commands = p.add_subparsers(dest="command", required=True)
    s = commands.add_parser("solve", help="find one feasible schedule; emit result and checked run sheets")
    s.add_argument("plan")
    s.add_argument("--out", required=True, help="new output directory; existing paths are refused")
    s.add_argument("--node-limit", type=int, default=10000, help="1..200000 propagated networks; default 10000")
    c = commands.add_parser("check", help="independently check every task, link, bound and resource pair")
    c.add_argument("plan")
    c.add_argument("schedule")
    r = commands.add_parser("report", help="check a schedule, then export CSV and printable offline HTML")
    r.add_argument("plan")
    r.add_argument("schedule")
    r.add_argument("--out", required=True)
    e = commands.add_parser("example", help="write an installed example without needing the source checkout")
    e.add_argument("--name", choices=["mixed-run", "pinned-run", "impossible"], default="mixed-run")
    e.add_argument("--out", required=True, help="new JSON file")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "example":
            data = importlib.resources.files("bench_window").joinpath("data", args.name + ".json").read_text(encoding="utf-8")
            write_new(args.out, data)
            print(f"Wrote {args.name} example to {args.out}")
            return 0
        plan = load_plan(args.plan)
        if args.command == "solve":
            result = solve(plan, args.node_limit)
            files = {"result.json": encode(result)}
            if result["status"] == "feasible":
                csv, markup = run_sheet(plan, result)
                files.update({"schedule.csv": csv, "run-sheet.html": markup})
            publish(args.out, files)
            print(encode({"status": result["status"], "explored_nodes": result["explored_nodes"], "output": str(args.out)}), end="")
            return {"feasible": 0, "infeasible": 3, "search_limit": 4}[result["status"]]
        result = read_json(args.schedule)
        errors = check_schedule(plan, result)
        if args.command == "check" or errors:
            print(encode({"valid": not errors, "errors": errors}), end="")
            return 5 if errors else 0
        csv, markup = run_sheet(plan, result)
        publish(args.out, {"schedule.csv": csv, "run-sheet.html": markup})
        print(f"Checked run sheets written to {args.out}")
        return 0
    except (PlanError, OSError, ValueError) as exc:
        print(f"bench-window: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("bench-window: interrupted; no feasible result asserted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
