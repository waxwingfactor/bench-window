"""Escaped, self-contained run sheets. No scripts, fonts, or network requests."""

import csv
import html
import io
from string import Template


def elapsed(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def spreadsheet_text(value):
    # CSV quoting alone does not prevent spreadsheet formula interpretation.
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def run_sheet(plan, result):
    order = sorted(plan["tasks"], key=lambda t: (result["starts"][t["id"]], t["id"]))
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["task", "label", "start_seconds", "end_seconds", "start_elapsed", "end_elapsed", "resources", "fixed_start"])
    rows = []
    esc = html.escape
    for task in order:
        tid = task["id"]
        start = result["starts"][tid]
        end = start + task["duration"]
        fixed = "observed / fixed" if "fixed_start" in task else "planned"
        writer.writerow([tid, spreadsheet_text(task["label"]), start, end, elapsed(start), elapsed(end),
                         ";".join(task["resources"]), task.get("fixed_start", "")])
        rows.append(f"<tr><td><strong>{esc(tid)}</strong><br><span>{esc(task['label'])}</span></td>"
                    f"<td>{elapsed(start)}</td><td>{elapsed(end)}</td>"
                    f"<td>{esc(', '.join(task['resources']) or 'No exclusive resource')}</td><td>{fixed}</td></tr>")
    gap_rows = []
    lookup = {t["id"]: t for t in plan["tasks"]}
    for link in plan["links"]:
        a, b = link["before"], link["after"]
        gap = result["starts"][b] - result["starts"][a] - lookup[a]["duration"]
        maximum = str(link["max_gap"]) if "max_gap" in link else "unbounded"
        gap_rows.append(f"<tr><td>{esc(a)} → {esc(b)}</td><td>{gap}</td><td>{link['min_gap']}</td><td>{maximum}</td></tr>")
    markup = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>Run sheet — TITLE</title><style>
:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#eef3f2;color:#142d34;font:16px/1.55 system-ui,sans-serif}
main{max-width:1100px;margin:auto;padding:44px 28px}header{border-top:6px solid #12695e;padding-top:22px}.kicker{letter-spacing:.13em;font-size:.76rem;font-weight:750;color:#12695e}
h1{font-size:clamp(1.8rem,5vw,2.8rem);line-height:1.15;margin:12px 0 20px;overflow-wrap:anywhere}h2{font-size:1.15rem;margin-top:30px}
.note{padding:18px 20px;background:#fff;border-left:4px solid #12695e}.meta{font-size:.85rem;color:#385b63;overflow-wrap:anywhere}code{font-size:.78rem}
.scroll{overflow:auto;border:1px solid #c4d6d3;background:white}table{border-collapse:collapse;width:100%;min-width:650px;text-align:left}
th{font-size:.75rem;letter-spacing:.04em;background:#142d34;color:#fff}th,td{padding:14px 16px;vertical-align:top;border-bottom:1px solid #d9e3e1}
td:nth-child(2),td:nth-child(3){font-variant-numeric:tabular-nums;white-space:nowrap}td span{font-size:.9rem;color:#385b63}caption{text-align:left;padding:12px 16px;color:#385b63;font-size:.85rem}
footer{margin-top:28px;font-size:.85rem;color:#385b63}@media(max-width:600px){main{padding:24px 16px}.note{padding:14px}th,td{padding:12px}}
@media print{body{background:white;font-size:10pt}main{padding:0}.scroll{overflow:visible}table{min-width:0}tr{break-inside:avoid}thead{display:table-header-group}}
</style><main><header><div class="kicker">BENCH-WINDOW / MANUAL RUN SHEET</div><h1>TITLE</h1></header>
<div class="note"><strong>Feasible under the declared constraints.</strong> This is one feasible timetable, not an optimized timetable or evidence of scientific validity. All times are elapsed HH:MM:SS from your chosen run origin. Review the order and practical buffers before use.</div>
<p class="meta">Plan identity <code>HASH</code><br>Unfixed tasks start no earlier than NOW · horizon HORIZON · NODES search nodes</p>
<h2>Chronological tasks</h2><div class="scroll" tabindex="0" role="region" aria-label="Scrollable chronological task table"><table><caption>Half-open intervals: a resource may be handed over exactly at a task's end.</caption><thead><tr><th scope="col">Task / action</th><th scope="col">Start</th><th scope="col">End</th><th scope="col">Exclusive resources</th><th scope="col">Basis</th></tr></thead><tbody>ROWS</tbody></table></div>
<h2>Waiting-window check</h2><div class="scroll" tabindex="0" role="region" aria-label="Scrollable waiting-window table"><table><caption>Gaps run from the first task's end to the second task's start. Values below are seconds.</caption><thead><tr><th scope="col">Link</th><th scope="col">Scheduled gap</th><th scope="col">Minimum</th><th scope="col">Maximum</th></tr></thead><tbody>GAPS</tbody></table></div>
<footer>Static offline report · bench-window 1.0.0 · All bounds, durations, resource assignments and fixed observations were supplied by the planner. This sheet does not reserve equipment or observe actual execution.</footer></main></html>"""
    # Template substitution never scans inserted user values a second time.
    values = {"rows": "".join(rows), "gaps": "".join(gap_rows) or '<tr><td colspan="4">No waiting links declared.</td></tr>',
              "hash": result["plan_sha256"], "now": elapsed(plan["not_before"]),
              "horizon": elapsed(plan["horizon"]), "nodes": str(result["explored_nodes"]),
              "title": esc(plan["title"])}
    for token in values:
        markup = markup.replace(token.upper(), "${" + token + "}")
    return output.getvalue(), Template(markup).substitute(values)
