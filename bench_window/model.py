"""Strict, bounded input contract and normalized plan identity."""

import hashlib
import json
import re
import unicodedata
from pathlib import Path

MAX_BYTES = 262144
MAX_TASKS = 40
MAX_LINKS = 400
MAX_RESOURCES = 40
MAX_HORIZON = 604800
ID = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}\Z")


class PlanError(ValueError):
    """The input is outside the supported contract."""


def keys(obj, allowed, required, where):
    if not isinstance(obj, dict):
        raise PlanError(f"{where}: expected an object")
    unknown = set(obj) - set(allowed)
    missing = set(required) - set(obj)
    if unknown or missing:
        raise PlanError(f"{where}: unknown keys {sorted(unknown)}, missing keys {sorted(missing)}")


def integer(value, low, high, where):
    if type(value) is not int or not low <= value <= high:
        raise PlanError(f"{where}: expected integer in [{low}, {high}]")
    return value


def identifier(value, where):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise PlanError(f"{where}: use 1..64 ASCII letters/digits/._-, starting with a letter")
    return value


def label(value, where):
    if (not isinstance(value, str) or not value.strip() or len(value) > 160
            or any(unicodedata.category(c).startswith("C") for c in value)):
        raise PlanError(f"{where}: expected 1..160 visible characters")
    return value


def unique_ids(values, where, limit):
    if not isinstance(values, list) or len(values) > limit:
        raise PlanError(f"{where}: expected list with at most {limit} entries")
    out = [identifier(v, where) for v in values]
    if len(set(out)) != len(out):
        raise PlanError(f"{where}: duplicate identifiers")
    return sorted(out)


def validate_plan(raw):
    keys(raw, {"schema", "title", "horizon", "resources", "tasks", "links", "not_before"},
         {"schema", "title", "horizon", "resources", "tasks"}, "plan")
    integer(raw["schema"], 1, 1, "schema")
    horizon = integer(raw["horizon"], 1, MAX_HORIZON, "horizon")
    resources = unique_ids(raw["resources"], "resources", MAX_RESOURCES)
    now = integer(raw.get("not_before", 0), 0, horizon, "not_before")
    if not isinstance(raw["tasks"], list) or not 1 <= len(raw["tasks"]) <= MAX_TASKS:
        raise PlanError(f"tasks: expected 1..{MAX_TASKS} entries")
    tasks = []
    for task in raw["tasks"]:
        keys(task, {"id", "label", "duration", "resources", "release", "deadline", "fixed_start"},
             {"id", "duration", "resources"}, "task")
        tid = identifier(task["id"], "task.id")
        assigned = unique_ids(task["resources"], f"{tid}.resources", MAX_RESOURCES)
        if not set(assigned) <= set(resources):
            raise PlanError(f"{tid}: undeclared resource")
        t = {"id": tid, "label": label(task.get("label", tid), f"{tid}.label"),
             "duration": integer(task["duration"], 1, horizon, f"{tid}.duration"),
             "resources": assigned,
             "release": integer(task.get("release", 0), 0, horizon, f"{tid}.release"),
             "deadline": integer(task.get("deadline", horizon), 0, horizon, f"{tid}.deadline")}
        if "fixed_start" in task:
            t["fixed_start"] = integer(task["fixed_start"], 0, horizon, f"{tid}.fixed_start")
        tasks.append(t)
    tids = {t["id"] for t in tasks}
    if len(tids) != len(tasks):
        raise PlanError("tasks: duplicate task IDs")
    raw_links = raw.get("links", [])
    if not isinstance(raw_links, list) or len(raw_links) > MAX_LINKS:
        raise PlanError(f"links: expected at most {MAX_LINKS} entries")
    links = []
    pairs = set()
    for link in raw_links:
        keys(link, {"before", "after", "min_gap", "max_gap"}, {"before", "after"}, "link")
        before = identifier(link["before"], "link.before")
        after = identifier(link["after"], "link.after")
        if before not in tids or after not in tids or before == after:
            raise PlanError("link: endpoints must be different existing tasks")
        if (before, after) in pairs:
            raise PlanError("links: duplicate directed pair")
        pairs.add((before, after))
        gap = integer(link.get("min_gap", 0), 0, horizon, "min_gap")
        item = {"before": before, "after": after, "min_gap": gap}
        if "max_gap" in link:
            item["max_gap"] = integer(link["max_gap"], gap, horizon, "max_gap")
        links.append(item)
    return {"schema": 1, "title": label(raw["title"], "title"), "horizon": horizon,
            "not_before": now, "resources": resources,
            "tasks": sorted(tasks, key=lambda t: t["id"]),
            "links": sorted(links, key=lambda k: (k["before"], k["after"]))}


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise PlanError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value):
    raise PlanError(f"unsupported JSON numeric constant: {value}")


def read_json(path):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise PlanError(f"JSON exceeds {MAX_BYTES} bytes")
    try:
        return json.loads(data.decode("utf-8-sig"), object_pairs_hook=_pairs,
                          parse_constant=_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise PlanError(f"invalid UTF-8 JSON: {exc}") from exc


def load_plan(path):
    return validate_plan(read_json(path))


def plan_hash(plan):
    encoded = json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()
