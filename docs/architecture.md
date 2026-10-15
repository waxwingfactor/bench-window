# Architecture and supported boundaries

bench-window is a local Python 3.9+ command-line package with no runtime
dependencies. Its supported unit of work is one explicitly declared short
manual run. The public workflow is JSON plan → bounded feasibility search →
independent assignment check → JSON result and static CSV/HTML run sheets.
The [guide](guide.md) defines the complete file contract and exit codes.

## Modules and responsibilities

| Module | Responsibility |
| --- | --- |
| `model.py` | Bounded UTF-8 JSON reading, duplicate-key rejection, strict schema validation, defaults, deterministic ordering, normalized plan identity. |
| `solver.py` | Temporal propagation and binary search over conflicting exclusive-resource orders. |
| `checker.py` | Direct validation of a complete assignment without using the solver's graph construction or propagation. |
| `report.py` | Chronological CSV and escaped, self-contained printable HTML from a checked result. |
| `cli.py` | Installed examples, command dispatch, explicit result codes, and no-clobber local output. |
| `data/` | Constructed examples available from installed distributions without a checkout. |

All times are integer elapsed seconds from a user-selected origin. The
supported input has 1–40 tasks, 0–40 resources, at most 400 links, and a horizon
of 1–604,800 seconds. Each task has a fixed positive duration and holds every
listed resource for its full interval. No implicit physical or biological
semantics are attached to a task label or resource name.

## Temporal model

There is one start variable per task and an origin fixed at zero. A directed
weighted edge from U to V represents `start(V) >= start(U) + weight`.
Release times, latest finishes, fixed starts, and end-to-start lag bounds
translate into these difference constraints. Each unfixed task also receives a
lower bound of `not_before`. A fixed task still obeys its release, deadline,
links, and resource constraints, but can remain before `not_before`.

Propagation repeatedly increases lower bounds. A positive constraint cycle,
or a required origin above zero, contradicts the fixed origin. After
propagation settles, the start assignment satisfies the temporal network.
Because all coefficients and bounds are integers, these propagated starts
are integer seconds.

Temporal consistency alone does not ensure resource consistency. For every
pair of tasks sharing any named resource, their half-open occupied intervals
must be disjoint. If the propagated assignment contains a collision, the
solver branches into A-before-B and B-before-A, adding the relevant
end-to-start constraint. A nonpreemptive feasible schedule must satisfy one
of those two orders, so searching both covers that conflict without silently
discarding an ordering.

The search is deterministic and iterative. It stops when it finds one checked
assignment, exhausts the resource-order branches, or reaches the configured
node limit. The budget counts propagated networks including the root;
10,000 is the default and 200,000 is the maximum. It is not a wall-time or
memory limit. Hard instances can take substantially longer than easy ones
within the same task-count bound.

## Honest outcomes

- **`feasible`:** the candidate passed the separate checker. This asserts
  satisfaction of the declared model, with no makespan, regular-cadence,
  workload-balance, or optimality claim.
- **`infeasible`:** every branch in the complete resource-order search was
  rejected. No schedule satisfies the declared model.
- **`search_limit`:** unexplored branches remain. Feasibility is unknown;
  the program emits no partial timetable as success.

Only a feasible solve produces run sheets. Other solve outcomes produce a
diagnostic `result.json` alone. A short `last_conflict` trace can help locate
contradictions but is not a minimal unsatisfiable core. Unsupported or
malformed input fails before scheduling.

## Independent checking and plan identity

`checker.py` recomputes each task's start/end bounds, fixed-start equality,
`not_before` constraint, link gap, and every shared-resource interval pair
directly. It does not reuse temporal edges or the propagation routine. The
solver invokes it before returning success; the `check` and `report` commands
invoke it on supplied result files. It also requires the complete strict
feasible-result envelope and producer version `1.0.0`.

The result's `plan_sha256` is SHA-256 over compact, sorted-key JSON of the
validated normalized plan. Defaults are made explicit; tasks, links, and
resource lists are sorted. This permits harmless formatting/order changes
while binding a result to the actual normalized requirements. Title and labels
are included. This digest is an identity check, not an authenticated signature,
an execution audit trail, or proof of the truth of observations.

## Replanning preserves modeled history

There is no separate scheduler state or sensor feed. Replanning supplies
another complete plan with observed starts pinned using `fixed_start` and a
current-time lower bound using `not_before` for tasks that have not begun.
All historical tasks and links must remain present. Completed task durations
must reflect actual elapsed time when known; an ongoing duration is still a
user-supplied total-occupation estimate. Resource occupancy and link deadlines
are calculated from those durations.

A fixed start is not evidence of completion. An already violated window, an
incorrect observation, or an unknown actual duration can make the declared
history inconsistent. The solver neither infers missing physical events nor
relaxes a constraint to fabricate a recovery. Replanning finds any feasible
arrangement under the updated model; it does not minimize changes from the
previous timetable.

## Filesystem, data, and trust boundaries

Each JSON read is limited to 262,144 bytes. The parser rejects duplicate keys,
nonstandard numeric constants, unknown modeled keys, noninteger numeric
fields, and values outside explicit bounds. Labels reject control/format and
other Unicode category-C characters. These limits reduce accidental resource
exhaustion and ambiguous interpretation; they are not an isolation boundary
against hostile local users or every denial-of-service input.

The process reads the input paths you provide and writes only the requested
new output location. It has no authentication, telemetry, network client,
hardware drivers, or booking-system integration. Treat input observations and
constraints as untrusted claims until reviewed locally. Avoid sensitive data
in labels if you plan to share the resulting files.

`example` creates its file exclusively. `solve` and `report` first reserve a new
directory, then exclusively create their output files; existing paths,
including symlinks and empty directories, are refused. Missing parent
directories are not created. If a write raises an exception, cleanup attempts
to remove only files created by that call and its empty output directory.
This is not a durable transaction against power loss or a hard process kill;
inspect any interrupted output and use a fresh path for the next attempt.

The supported filesystem environment is a trusted local parent directory with
a single writer. Ancestor paths are not sandboxed, and the implementation
does not defend against hostile concurrent changes to parent directories or
provide distributed coordination on shared filesystems.

HTML escapes supplied text and makes no remote requests; its policy disables
script execution and permits only its embedded styling. CSV text beginning,
after leading whitespace, with `=`, `+`, `-`, or `@` receives a leading
apostrophe to reduce spreadsheet formula interpretation. The JSON result is
the schedule exchange format; CSV is a presentation export and is not accepted
as schedule input.

## Acceptance evidence and compatibility

The tests include a separately written exhaustive oracle that enumerates
integer starts on small problems without consulting either production solver
or checker. Seeded cases exercise satisfiable and contradictory resource,
time-window, fixed-start, and link combinations. Focused tests cover boundary
handoffs, simultaneous resource requirements, and historical tasks around
`not_before`. Contract, command, report, and distribution checks cover the
other supported interfaces.

The source distribution includes examples, tests, and Markdown documentation.
Development checks use the standard library's `unittest`; building a wheel and
source distribution needs the declared build tools. Release evidence separately
records tested environments and actual artifact installation results. A
declared Python requirement is not evidence that every OS/Python combination
has been tested.

The product supplies operational arithmetic and clear model outcomes. It does
not validate laboratory procedures, promise that a feasible irregular schedule
is comfortable to execute, or establish scientific validity, hardware safety,
regulatory compliance, adoption, or measured savings. The
[research record](research.md) documents existing alternatives and the bounded
reason for this scope.
