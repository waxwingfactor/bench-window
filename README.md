# bench-window

Offline timing feasibility and replanning for small manual laboratory runs.

Describe individually timed tasks, the people and equipment each task occupies,
and the allowed waiting windows between tasks. bench-window finds **one feasible
schedule**, independently checks its assignments, and writes a chronological CSV
and printable offline HTML run sheet. It can also check your edited schedule or
replan with observed task starts fixed in place.

Use it for small heterogeneous runs that need more than a regular staggering
interval. It accepts up to 40 tasks, 40 named exclusive resources, 400 directed
links, and a seven-day horizon, using integer elapsed seconds. It makes no
optimality claim. Irregular timings need practical review before use.

Python 3.9 or newer. MIT licensed. Pure Python with no runtime dependencies,
network calls, accounts, or background service. All example timings are
**constructed coordination examples**, not laboratory instructions.

## Install the release

Create a virtual environment, then install the wheel from the
[GitHub v1.0.0 release](https://github.com/waxwingfactor/bench-window/releases/tag/v1.0.0):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --no-deps https://github.com/waxwingfactor/bench-window/releases/download/v1.0.0/bench_window-1.0.0-py3-none-any.whl
.venv/bin/python -m bench_window --version
```

On Windows, create the environment with `py -3 -m venv .venv` and use
`.venv\Scripts\python.exe` wherever the examples use `.venv/bin/python`.
The distribution is published on GitHub; these instructions do not assume a
PyPI package. The release also contains a source distribution and verification
evidence.

## Run an installed example

The example is included in the wheel; no development checkout is needed. Start
in a directory where `plan.json`, `run`, and `reprint` do not already exist:

```sh
.venv/bin/python -m bench_window example --out plan.json
.venv/bin/python -m bench_window solve plan.json --out run
.venv/bin/python -m bench_window check plan.json run/result.json
.venv/bin/python -m bench_window report plan.json run/result.json --out reprint
```

Open `run/run-sheet.html` in a browser or print it. The HTML is a static local
document. `run/schedule.csv` gives elapsed seconds and HH:MM:SS values;
`run/result.json` is the machine-readable schedule. `check` prints
`"valid": true` only when every declared task, timing constraint, resource pair,
and plan identity passes.

`solve` requires a **new output directory** under an existing parent. Existing
paths, including empty directories, are refused. `example` similarly requires a
new file. Use trusted local paths with a single writer; the CLI does not create
missing parent directories.

## Model the run

Every task has a positive duration and an explicit list of resources. A task
requiring a person and a device occupies both for its whole duration. A passive
wait can use `"resources": []`; an unattended device operation should list the
device alone. Resources are exclusive, and tasks may hand one over exactly at
the preceding task's end.

A link's `min_gap` and optional `max_gap` run from the first task's **end** to the
next task's **start**. `release` is an earliest start; `deadline` is a latest
finish. All values are integer seconds from your chosen run origin, with no
wall-clock or timezone conversion. See the [input contract and guide](docs/guide.md).

For a constructed remaining-run example:

```sh
.venv/bin/python -m bench_window example --name pinned-run --out remaining.json
.venv/bin/python -m bench_window solve remaining.json --out remaining-run
```

When replanning your own run, retain every completed and running task, set its
`fixed_start` to the observed start, and use its actual completed duration where
known. Set `not_before` to the current elapsed time for tasks that have not
started. A fixed start is not a completion record: unknown or inaccurate
durations can make the result misleading or infeasible. The tool cannot infer
what physically happened. The [replanning procedure](docs/guide.md#replan-after-a-delay)
explains this in detail.

## Read the result correctly

| Outcome | Exit code | Meaning |
| --- | --- | --- |
| `feasible` | 0 | One complete assignment passed the independent checker. |
| Invalid input, argument, or file operation | 2 | Correct the reported contract or path error. |
| `infeasible` | 3 | No schedule satisfies all declared constraints. |
| `search_limit` | 4 | Feasibility remains unknown; no schedule is asserted. |
| Failed schedule check | 5 | The schedule does not satisfy the plan/result contract. |
| Interrupted | 130 | No feasible result is asserted by the interrupted command. |

An `infeasible` or `search_limit` solve writes only `result.json`, without a CSV
or HTML run sheet. The default search budget is 10,000 propagated networks;
`--node-limit` accepts 1–200,000. A larger limit can take substantially longer.
The diagnostic trail is not a minimal explanation of every conflict.

## Scope and evidence

The planner checks user-declared operational constraints. It does not prescribe
protocols, validate scientific outcomes, observe execution, reserve equipment,
control hardware, or supply compliance certification. It does not infer setup,
cleanup, travel, breaks, resource availability, or safety margins: declare them
as tasks, bounds, or fixed blocks where appropriate.

Existing alternatives are strong: use [StaggR](https://github.com/amfrancette/StaggR)
for regular identical sample runs, and evaluate established scheduling libraries
or orchestration platforms for broader needs. The dated
[research and positioning record](docs/research.md) distinguishes documented
problems from inferred demand, with modest opportunity confidence and no
customer-adoption claim. See also the [architecture](docs/architecture.md).

## Source installation and development

Download `bench_window-1.0.0.tar.gz` from the release and install it in a virtual
environment with `python -m pip install /path/to/bench_window-1.0.0.tar.gz`.
Building from source needs setuptools and wheel as declared in
`pyproject.toml`; build isolation may download them. The installed program has
no runtime dependencies and operates offline.

From an extracted source distribution or a clone:

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
python -m pip install build
python -m build
```

Tests include an independent exhaustive oracle for small integer scheduling
problems, plus contract, CLI, reporting, and distribution checks. Release-specific
verification results belong to the published release evidence; a test suite is
not scientific validation. Report reproducible issues through
[GitHub Issues](https://github.com/waxwingfactor/bench-window/issues).
