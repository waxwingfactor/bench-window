# User guide and input contract

bench-window plans one bounded manual run from explicit operational
requirements. It produces a feasible timetable or a clear non-success result,
and checks saved timetables independently of the planner. It uses elapsed
integer seconds, not calendar timestamps.

All examples in this guide and the installed example files are **constructed**.
Their values illustrate coordination only; they are not recommended laboratory
procedures or evidence of real use.

## Installed workflow

After installing the [v1.0.0 wheel](https://github.com/waxwingfactor/bench-window/releases/tag/v1.0.0)
in a virtual environment, use its Python interpreter for these commands:

```sh
python -m bench_window example --out plan.json
python -m bench_window solve plan.json --out run
python -m bench_window check plan.json run/result.json
python -m bench_window report plan.json run/result.json --out printable
```

The equivalent `bench-window` console command is installed in the same
environment. `python -m bench_window` makes the selected environment explicit.

`example` can write `mixed-run` (the default), `pinned-run`, or `impossible`:

```sh
python -m bench_window example --name impossible --out impossible.json
python -m bench_window solve impossible.json --out impossible-result
```

The second command intentionally exits 3 and writes only
`impossible-result/result.json`. Do not treat that expected nonzero exit as a
usable timetable. Run examples one command at a time if your shell or script
stops on nonzero exit codes.

Choose new output names on each attempt. The CLI refuses to overwrite files or
directories, even empty ones. An output parent must already exist; for example,
create `results` yourself before requesting `--out results/run-01`. Use a
trusted local directory controlled by one writer. Avoid shared/network folders
and concurrent processes manipulating the same paths.

## A small complete plan

Save this constructed plan as `short.json`:

```json
{
  "schema": 1,
  "title": "Constructed short coordination example",
  "horizon": 900,
  "resources": ["operator", "reader"],
  "tasks": [
    {"id": "prepare", "duration": 60, "resources": ["operator"]},
    {"id": "wait", "duration": 300, "resources": []},
    {
      "id": "read",
      "duration": 60,
      "resources": ["operator", "reader"],
      "release": 420,
      "deadline": 600
    }
  ],
  "links": [
    {"before": "prepare", "after": "wait", "max_gap": 0},
    {"before": "wait", "after": "read", "min_gap": 60, "max_gap": 120}
  ]
}
```

```sh
python -m bench_window solve short.json --out short-run
python -m bench_window check short.json short-run/result.json
```

In this constructed example, a valid arrangement is preparation at 0–60, a wait
at 60–360, and reading at 420–480 seconds. The first link requires an immediate
handoff. The second permits 60–120 seconds between the wait's end and reading's
start. During the resource-free wait, the operator is available for other
declared tasks.

The planner may rearrange tasks and returns one feasible arrangement. Input
array order is not an execution order or priority. Declare every required order
with links; do not rely on IDs or labels.

## Plan fields

Unknown keys are rejected at every modeled level. Names such as `notes`,
`units`, or `completed` are not supported fields. JSON must be UTF-8; an initial
UTF-8 byte-order mark is accepted. Each input file, including a schedule passed
to `check` or `report`, is limited to 262,144 bytes. Duplicate object keys,
invalid JSON, and nonstandard numeric constants are rejected. Integer fields
do not accept decimals, strings, or JSON booleans.

| Top-level field | Required | Meaning and bounds |
| --- | --- | --- |
| `schema` | Yes | Integer `1`. |
| `title` | Yes | Nonblank string, at most 160 characters; Unicode control/format and other category-C characters are rejected. |
| `horizon` | Yes | Integer 1–604,800 seconds; all tasks must finish within it. |
| `resources` | Yes | List of 0–40 unique resource IDs. |
| `tasks` | Yes | List of 1–40 tasks with unique task IDs. |
| `links` | No | List of at most 400 directed links; defaults to `[]`. |
| `not_before` | No | Integer 0–`horizon`, default 0; earliest start for every task without `fixed_start`. |

Task and resource IDs use 1–64 ASCII characters. They start with a letter and
then contain letters, digits, `.`, `_`, or `-`. IDs are case-sensitive.

| Task field | Required | Meaning and bounds |
| --- | --- | --- |
| `id` | Yes | Unique task ID. |
| `duration` | Yes | Integer 1–`horizon`; fixed, uninterrupted occupation time. |
| `resources` | Yes | Unique declared resource IDs occupied simultaneously for the entire task; `[]` is allowed. |
| `label` | No | Same string rules as `title`; defaults to the task ID. |
| `release` | No | Earliest start, integer 0–`horizon`; default 0. |
| `deadline` | No | Latest finish, integer 0–`horizon`; default `horizon`. |
| `fixed_start` | No | Exact start, integer 0–`horizon`; still subject to release, deadline, links, and resource constraints. |

Bounds are inclusive. A task with release 100, duration 60, and deadline 160
must start at exactly 100. A structurally valid but impossible combination
(such as a deadline earlier than the task can finish) produces `infeasible`,
not a silently shortened task.

| Link field | Required | Meaning and bounds |
| --- | --- | --- |
| `before` | Yes | Existing predecessor task ID. |
| `after` | Yes | Different existing successor task ID. |
| `min_gap` | No | Minimum end-to-start gap, integer 0–`horizon`; default 0. |
| `max_gap` | No | Maximum end-to-start gap, integer `min_gap`–`horizon`; omitted means no additional upper gap bound. |

For link A → B, the gap is `start(B) - start(A) - duration(A)`. Equal minimum
and maximum encode an exact gap. A maximum of zero with the default minimum
requires B to start exactly when A ends. Duplicate directed pairs and self-links
are rejected. Contradictory directed cycles are infeasible.

## Represent resources and waiting accurately

Every named resource has capacity one. A task listing `["operator", "reader"]`
needs both for its full interval; listing two readers means occupying both,
not choosing either. There is no automatic choice among interchangeable staff
or devices, preemption, batching, or fractional capacity.

A passive wait with no constrained equipment can use `"resources": []`. To
hold a device while its operator is free, create a device-only task between
the loading and unloading tasks. The installed `mixed-run` example models
this explicitly. A waiting link by itself holds no resource.

Intervals are half-open: `[start, start + duration)`. Two tasks sharing a
resource can touch at a boundary, but they cannot overlap for even one second.
The model assumes immediate handover unless you declare handling or cleanup
time. Include setup, travel, cleanup, breaks, and availability blocks as
appropriate. A fixed resource-only task can represent an existing unavailable
interval, but it does not create or update a booking in another system.

## Replan after a delay

Replanning is another `solve` with an updated plan. The tool has no execution
monitor or completion-status database. Preserve the original elapsed-time
origin, keep **all completed and running tasks and their links**, and update a
copy of the plan:

1. Give every task that has started its actual `fixed_start`.
2. For each completed task, change `duration` to its actual elapsed duration
   when it differed from the plan. Later links are measured from that modeled
   end. A fixed start alone does not establish when the task ended.
3. For an ongoing task, retain the observed start and supply a reviewed duration
   representing its expected total occupation. If the end is unknown, the
   output remains conditional on that estimate; the tool cannot infer it.
4. Set top-level `not_before` to the current elapsed time. It constrains only
   tasks without `fixed_start`; fixed historical tasks remain in place.
5. Review releases, deadlines, links, and resource assignments against what
   actually happened, then solve into a new directory and check that result.

For the constructed `short.json` plan above, suppose preparation actually took
90 seconds, the wait then began at second 90, and the current elapsed time is
400. Keep all three tasks and both links; set preparation's `fixed_start` to 0
and `duration` to 90, set the wait's `fixed_start` to 90, retain its completed
duration of 300, and add `"not_before": 400` at the top level. A possible reading
start is then 450. These are invented observations solely to illustrate the
contract.

```sh
python -m bench_window solve updated-short.json --out updated-run
python -m bench_window check updated-short.json updated-run/result.json
```

You can also export and solve the constructed installed replan:

```sh
python -m bench_window example --name pinned-run --out remaining.json
python -m bench_window solve remaining.json --out remaining-run
```

Do not remove past tasks to force success: doing so can erase occupied
resources and time-window relationships. Unknown observations, changed actual
durations, missed deadlines, or an already broken maximum gap can make the
complete model infeasible. That result may describe a real violation or an
incorrect input; bench-window cannot decide which happened physically. Review
the observations and local procedure rather than assuming an automatic repair
is possible.

## Results, checks, and reports

A successful `solve` creates three files:

- `result.json`: schema, producer version, `status`, normalized plan digest,
  explored-node count, and one start per task.
- `schedule.csv`: chronological rows with start/end seconds, elapsed HH:MM:SS,
  labels, resources, and fixed-start values.
- `run-sheet.html`: self-contained printable tables with timing-window checks.

HTML contains no scripts or remote assets and works without a server. It is a
static report, with no live timers, alarms, or execution updates. Review human
readability and practical buffers; mathematical feasibility is not a guarantee
that an irregular sequence is comfortable to execute.

`check` evaluates all timing constraints and every pair sharing a resource.
It also verifies the result envelope: schema 1, producer version `1.0.0`,
`status: "feasible"`, valid explored-node count, matching `plan_sha256`, and
exactly the declared task IDs with integer starts. Unknown result fields are
rejected. `report` performs the same check before exporting only CSV and HTML
to its new output directory. Neither command edits your input files.

You may copy a feasible `result.json`, edit its `starts`, and check it against
the unchanged plan. Keep the envelope fields intact. If the plan changes,
solve it again: its old result should fail the identity check.

`plan_sha256` identifies the **normalized plan**, not its raw file bytes.
Normalization supplies defaults and sorts tasks, links, and resource lists;
whitespace, object-key order, and those list orders do not change the digest.
Substantive changes, including labels and title, do. Unicode text is not
normalized to another spelling. The digest is not a signature or proof that
the declared observations are true.

| Exit | Meaning |
| --- | --- |
| 0 | Successful example, feasible solve, valid check, or successful checked report. |
| 2 | Invalid CLI arguments, invalid plan/JSON, or input/output operation failure. |
| 3 | Exhaustive resource-order search proved the declared plan infeasible. |
| 4 | Search budget exhausted; feasibility remains unknown. |
| 5 | A parsed schedule failed the schedule contract or direct checks. |
| 130 | Keyboard interrupt; no feasible result asserted by the interrupted command. |

Malformed schedule JSON is an input error (2), while a parsed but invalid
schedule is a failed check (5). `infeasible` and `search_limit` solves produce
only `result.json`; that diagnostic result is not a schedule for `check` or
`report`. The last-conflict messages are a short search trace, not a minimal
unsatisfiable subset or a complete list of causes.

The default node limit is 10,000. To make a larger bounded attempt:

```sh
python -m bench_window solve plan.json --node-limit 200000 --out larger-search
```

The allowed range is 1–200,000. Nodes count propagated constraint networks,
including the root, not seconds. Runtime can grow substantially on hard
resource-ordering problems. Use a new output path and retain earlier
diagnostics for comparison.

## Scope and further reading

The supported model has fixed positive task durations, exclusive named
resources, elapsed seconds, inclusive windows, and nonnegative end-to-start
lags. It has no conditional branches, variable durations, resource alternatives,
recurring calendars, timezone handling, hardware drivers, automatic bookings,
or scientific interpretation. Your declared constraints must cover the actual
workflow; omitted requirements are not checked.

See [architecture and trust boundaries](architecture.md), the
[bounded research and alternatives](research.md), and the
[release evidence](https://github.com/waxwingfactor/bench-window/releases/tag/v1.0.0).
