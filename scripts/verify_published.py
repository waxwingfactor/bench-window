#!/usr/bin/env python3
"""Independently download and exercise the ACTUAL public GitHub release.

Requires Python 3.9+, venv/ensurepip, and public HTTPS access. No Git checkout,
GitHub token, editable install, or third-party verifier dependency is required.
The wheel install is offline; the sdist build may fetch its build dependencies
from public PyPI. Test commands use isolated installed Python environments.

Example (replace the source revision with the exact release commit):
    python scripts/verify_published.py --expected-source FULL_COMMIT_SHA \
        --work-dir /tmp/bench-window-public-check --output public-verification.json

Hashes establish agreement between downloaded assets, SHA256SUMS, and the
release's build metadata. This is not an independently reproducible build or a
cryptographic attestation that those assets were produced from that source.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.parse
import urllib.request


REPOSITORY = "waxwingfactor/bench-window"
TAG = "v1.0.0"
MAX_METADATA_BYTES = 2 * 1024 * 1024
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
CHECKOUT_ROOT = Path(__file__).resolve().parents[1]

# This guards Python socket creation/name resolution in the tested process. It
# is deliberately described as an injected socket guard, not an OS firewall.
SOCKET_GUARD = r'''
import runpy, socket, sys
def blocked(*args, **kwargs):
    raise RuntimeError("verification socket guard: network is disabled")
socket.socket = blocked
socket.create_connection = blocked
socket.getaddrinfo = blocked
socket.gethostbyname = blocked
socket.gethostbyname_ex = blocked
try:
    socket.create_connection(("example.invalid", 443))
except RuntimeError:
    pass
else:
    raise AssertionError("network guard failed its self-check")
sys.argv = ["bench-window"] + sys.argv[1:]
runpy.run_module("bench_window", run_name="__main__")
'''

INSTALLED_PROBE = r'''
import importlib.metadata, json, pathlib, site, sys
import bench_window
prefix = pathlib.Path(sys.prefix).resolve()
module = pathlib.Path(bench_window.__file__).resolve()
relative = module.relative_to(prefix)
print(json.dumps({
    "module_relative_to_environment": relative.as_posix(),
    "version": importlib.metadata.version("bench-window"),
    "runtime_requirements": importlib.metadata.requires("bench-window") or [],
    "isolated_mode": bool(sys.flags.isolated),
    "user_site_enabled": site.ENABLE_USER_SITE,
    "python": sys.version.split()[0]
}, sort_keys=True))
'''


class VerificationFailure(RuntimeError):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def within(path, parent):
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def public_json(url):
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "bench-window-public-verifier/1.0",
    })
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read(MAX_METADATA_BYTES + 1)
    if len(payload) > MAX_METADATA_BYTES:
        raise VerificationFailure("Public API response exceeded the metadata size limit")
    return json.loads(payload.decode("utf-8"))


def download(url, destination):
    request = urllib.request.Request(url, headers={"User-Agent": "bench-window-public-verifier/1.0"})
    count = 0
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("xb") as target:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            count += len(block)
            if count > MAX_ARTIFACT_BYTES:
                raise VerificationFailure("Release asset exceeded the download size limit")
            target.write(block)
    return count


def parse_manifest(path):
    entries = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64}) [ *]([A-Za-z0-9_.-]+)", line)
        if not match or match[2] in entries:
            raise VerificationFailure("SHA256SUMS contains a malformed or duplicate entry")
        entries[match[2]] = match[1]
    return entries


def extract_source(archive, destination):
    """Extract only bounded regular files/directories; never trust tar paths."""
    destination.mkdir()
    seen = set()
    roots = set()
    total = 0
    with tarfile.open(archive, "r:gz") as source:
        members = source.getmembers()
        if not members or len(members) > 5000:
            raise VerificationFailure("Source archive member count is outside the supported bound")
        for member in members:
            name = member.name
            path = PurePosixPath(name)
            if (not name or path.is_absolute() or "\\" in name or ":" in name
                    or any(part in ("..", "") for part in path.parts)
                    or name in seen or not (member.isfile() or member.isdir())):
                raise VerificationFailure("Unsafe, duplicate, linked, or unsupported source archive member")
            seen.add(name)
            roots.add(path.parts[0])
            total += member.size
            if total > MAX_ARTIFACT_BYTES or member.size < 0:
                raise VerificationFailure("Source archive expanded size exceeds the supported bound")
            target = destination.joinpath(*path.parts)
            if not within(target.resolve(), destination.resolve()):
                raise VerificationFailure("Source archive member escapes extraction directory")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                incoming = source.extractfile(member)
                if incoming is None:
                    raise VerificationFailure("Could not read a regular source archive member")
                with incoming, target.open("xb") as output:
                    shutil.copyfileobj(incoming, output)
    if len(roots) != 1:
        raise VerificationFailure("Source archive must have one top-level project directory")
    return destination / roots.pop()


class Verifier:
    def __init__(self, args):
        self.args = args
        self.work = args.work_dir
        self.logs = self.work / "private-logs"
        self.logs.mkdir()
        self.counter = 0
        self.evidence = {
            "schema": 1, "product": "bench-window", "repository": REPOSITORY, "tag": TAG,
            "expected_source_revision": args.expected_source,
            "started_at": utc_now(), "status": "running",
            "verification_environment": {"system": platform.system(), "release": platform.release(),
                                         "machine": platform.machine(), "python": platform.python_version(),
                                         "implementation": platform.python_implementation()},
            "provenance_scope": "Anonymous downloads of actual public release assets; exact public tag commit and declared build source checked; artifact hashes compared with manifest and build metadata. Not a reproducible-build or signed provenance claim.",
            "network_scope": "Artifact download and sdist build-dependency fetch require HTTPS. Relocated installed-package CLI checks use an injected, self-tested Python socket guard; this is not an OS network sandbox.",
            "checks": [], "commands": [], "installed_artifacts": [],
        }

    def require(self, condition, label):
        self.evidence["checks"].append({"check": label, "passed": bool(condition)})
        if not condition:
            raise VerificationFailure(label)

    def clean_env(self, task_env_dir):
        task_env_dir.mkdir(parents=True, exist_ok=True)
        keep = {"PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP", "TMPDIR",
                "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR"}
        env = {key: value for key, value in os.environ.items() if key.upper() in keep}
        env.update({"XDG_CONFIG_HOME": str(task_env_dir / "config"), "XDG_CACHE_HOME": str(task_env_dir / "cache"),
                    "PYTHONNOUSERSITE": "1", "PYTHONUTF8": "1", "PIP_CONFIG_FILE": os.devnull,
                    "PIP_DISABLE_PIP_VERSION_CHECK": "1", "PIP_NO_INPUT": "1",
                    "PIP_INDEX_URL": "https://pypi.org/simple"})
        return env

    def run(self, label, command, cwd, env, expected=0, category="installed_artifact", offline=False):
        self.counter += 1
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=600)
        log_base = self.logs / f"{self.counter:03d}"
        log_base.with_suffix(".stdout.txt").write_text(result.stdout, encoding="utf-8")
        log_base.with_suffix(".stderr.txt").write_text(result.stderr, encoding="utf-8")
        self.evidence["commands"].append({
            "step": label, "category": category, "expected_exit_code": expected,
            "observed_exit_code": result.returncode, "passed": result.returncode == expected,
            "isolated_python": "-I" in command, "injected_socket_guard": offline,
        })
        if result.returncode != expected:
            raise VerificationFailure(f"{label}: expected exit {expected}, observed {result.returncode}; private diagnostic logs retained in verification work directory")
        return result

    def resolve_tag(self):
        api = f"https://api.github.com/repos/{REPOSITORY}"
        reference = public_json(api + "/git/ref/tags/" + urllib.parse.quote(TAG, safe=""))
        obj = reference["object"]
        for _ in range(5):
            if obj.get("type") == "commit":
                return obj["sha"]
            self.require(obj.get("type") == "tag", "Public release tag refers to a commit or annotated tag")
            obj = public_json(api + "/git/tags/" + obj["sha"])["object"]
        raise VerificationFailure("Public tag annotation nesting exceeded the supported bound")

    def fetch_assets(self):
        release = public_json(f"https://api.github.com/repos/{REPOSITORY}/releases/tags/{TAG}")
        self.require(release.get("tag_name") == TAG and not release.get("draft"),
                     "Actual release is publicly visible under the expected tag")
        tag_revision = self.resolve_tag()
        self.require(tag_revision == self.args.expected_source, "Public release tag resolves to the expected exact source revision")
        self.evidence["public_release"] = {
            "url": release["html_url"], "release_id": release["id"],
            "published_at": release.get("published_at"), "tag_source_revision": tag_revision,
            "prerelease": release.get("prerelease", False),
        }
        assets = release.get("assets", [])
        wheels = [a for a in assets if a.get("name", "").endswith(".whl")]
        sdists = [a for a in assets if a.get("name", "").endswith(".tar.gz")]
        self.require(len(wheels) == len(sdists) == 1, "Actual release contains exactly one wheel and one source distribution")
        names = [wheels[0]["name"], sdists[0]["name"], "SHA256SUMS", "build-info.json"]
        downloads = self.work / "downloaded-assets"
        downloads.mkdir()
        paths = {}
        summaries = []
        for name in names:
            candidates = [a for a in assets if a.get("name") == name]
            self.require(len(candidates) == 1 and re.fullmatch(r"[A-Za-z0-9_.-]+", name),
                         "Release asset is present once with a safe basename: " + name)
            asset = candidates[0]
            expected_url = f"https://github.com/{REPOSITORY}/releases/download/{TAG}/{name}"
            self.require(asset.get("browser_download_url") == expected_url,
                         "Release download URL belongs to the expected public repository: " + name)
            target = downloads / name
            size = download(expected_url, target)
            self.require(size == asset.get("size"), "Downloaded asset size matches the public release metadata: " + name)
            paths[name] = target
            summaries.append({"name": name, "url": expected_url, "bytes": size, "sha256": sha256(target)})
        self.evidence["downloaded_assets"] = summaries
        manifest = parse_manifest(paths["SHA256SUMS"])
        build = json.loads(paths["build-info.json"].read_text(encoding="utf-8"))
        self.require(build.get("source_revision") == self.args.expected_source,
                     "Published build-info declares the expected exact source revision")
        artifact_hashes = build.get("artifacts")
        self.require(isinstance(artifact_hashes, dict), "Published build-info contains artifact digests")
        for name in names[:2]:
            digest = sha256(paths[name])
            self.require(manifest.get(name) == digest, "Downloaded digest matches SHA256SUMS: " + name)
            self.require(artifact_hashes.get(name) == digest, "Downloaded digest matches build-info: " + name)
        self.evidence["source_revision"] = build["source_revision"]
        self.evidence["published_build"] = {key: build.get(key) for key in ("python", "system", "workflow", "run_id")}
        return paths[names[0]], paths[names[1]]

    def cli(self, python, env, cwd, label, *arguments, expected=0, offline=False):
        command = [str(python), "-I"]
        command += ["-c", SOCKET_GUARD] if offline else ["-m", "bench_window"]
        command += list(arguments)
        return self.run(label, command, cwd, env, expected=expected, offline=offline)

    def verify_install(self, kind, artifact):
        base = self.work / kind
        base.mkdir()
        env = self.clean_env(base / "isolated-home")
        environment = base / "environment"
        self.run(kind + ": create fresh venv", [sys.executable, "-I", "-m", "venv", str(environment)],
                 base, env, category="environment_setup")
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        install = [str(python), "-I", "-m", "pip", "--isolated", "--disable-pip-version-check",
                   "install", "--no-deps", "--no-cache-dir", "--no-input"]
        install += ["--no-index"] if kind == "wheel" else ["--index-url", "https://pypi.org/simple"]
        install.append(str(artifact))
        self.run(kind + ": install actual downloaded artifact without dependencies", install, base, env,
                 category="artifact_installation")
        probe = self.run(kind + ": isolated installed-module location", [str(python), "-I", "-c", INSTALLED_PROBE], base, env)
        installed = json.loads(probe.stdout)
        self.require(installed["version"] == "1.0.0" and installed["isolated_mode"]
                     and not installed["user_site_enabled"] and not installed["runtime_requirements"],
                     kind + ": expected version, isolated imports, disabled user site, and no runtime dependencies")
        self.require("site-packages/bench_window/" in installed["module_relative_to_environment"],
                     kind + ": imported package resides inside the fresh environment outside the checkout")
        self.evidence["installed_artifacts"].append({"artifact": artifact.name, "kind": kind, **installed})
        self.exercise_installed(kind, python, env, base)
        return python, env, base

    def exercise_installed(self, kind, python, env, base):
        workflow = base / "initial-working-directory"
        workflow.mkdir()
        for name in ("mixed-run", "pinned-run", "impossible"):
            self.cli(python, env, workflow, kind + ": installed example " + name,
                     "example", "--name", name, "--out", name + ".json")
        self.cli(python, env, workflow, kind + ": feasible mixed-run solve", "solve", "mixed-run.json", "--out", "solved")
        result = json.loads((workflow / "solved/result.json").read_text(encoding="utf-8"))
        self.require(result["status"] == "feasible", kind + ": installed solve asserts feasibility")
        check = self.cli(python, env, workflow, kind + ": mixed-run independent check", "check", "mixed-run.json", "solved/result.json")
        self.require(json.loads(check.stdout) == {"valid": True, "errors": []}, kind + ": independent checker accepts installed mixed-run result")
        self.cli(python, env, workflow, kind + ": checked CSV and HTML report", "report", "mixed-run.json", "solved/result.json", "--out", "report")
        self.require(sorted(p.name for p in (workflow / "report").iterdir()) == ["run-sheet.html", "schedule.csv"],
                     kind + ": checked report contains the two supported exports")
        report_digests = {name: sha256(workflow / "report" / name) for name in ("run-sheet.html", "schedule.csv")}
        self.cli(python, env, workflow, kind + ": remaining-run replan", "solve", "pinned-run.json", "--out", "remaining")
        self.cli(python, env, workflow, kind + ": remaining-run independent check", "check", "pinned-run.json", "remaining/result.json")
        pinned = json.loads((workflow / "pinned-run.json").read_text(encoding="utf-8"))
        remaining = json.loads((workflow / "remaining/result.json").read_text(encoding="utf-8"))
        pins_preserved = all(remaining["starts"][task["id"]] == task["fixed_start"]
                             for task in pinned["tasks"] if "fixed_start" in task)
        future_preserved = all(remaining["starts"][task["id"]] >= pinned["not_before"]
                               for task in pinned["tasks"] if "fixed_start" not in task)
        self.require(pins_preserved and future_preserved, kind + ": fixed observations retained and future tasks respect not_before")
        self.cli(python, env, workflow, kind + ": impossible run exit 3", "solve", "impossible.json", "--out", "impossible", expected=3)
        self.require(sorted(p.name for p in (workflow / "impossible").iterdir()) == ["result.json"],
                     kind + ": infeasible run emits result only")
        impossible = json.loads((workflow / "impossible/result.json").read_text(encoding="utf-8"))
        self.require(impossible["status"] == "infeasible" and "starts" not in impossible,
                     kind + ": infeasible result does not assert task starts")
        tiny = {"schema": 1, "title": "Published artifact verification", "horizon": 4, "resources": ["bench"],
                "tasks": [{"id": "a", "duration": 2, "resources": ["bench"]},
                          {"id": "b", "duration": 2, "resources": ["bench"]}], "links": []}
        (workflow / "tiny.json").write_text(json.dumps(tiny), encoding="utf-8")
        self.cli(python, env, workflow, kind + ": exhausted search exit 4", "solve", "tiny.json", "--node-limit", "1", "--out", "limited", expected=4)
        limited = json.loads((workflow / "limited/result.json").read_text(encoding="utf-8"))
        self.require(sorted(p.name for p in (workflow / "limited").iterdir()) == ["result.json"]
                     and limited["status"] == "search_limit" and "starts" not in limited,
                     kind + ": exhausted search emits uncertainty and result only")
        self.cli(python, env, workflow, kind + ": tiny plan solve", "solve", "tiny.json", "--out", "tiny-solved")
        corrupted = json.loads((workflow / "tiny-solved/result.json").read_text(encoding="utf-8"))
        corrupted["starts"] = {"a": 0, "b": 1}
        (workflow / "corrupted.json").write_text(json.dumps(corrupted), encoding="utf-8")
        tamper = self.cli(python, env, workflow, kind + ": corrupted candidate exit 5", "check", "tiny.json", "corrupted.json", expected=5)
        self.require(not json.loads(tamper.stdout)["valid"], kind + ": checker rejects modified overlapping task starts")
        self.cli(python, env, workflow, kind + ": corrupted candidate cannot export", "report", "tiny.json", "corrupted.json", "--out", "corrupt-report", expected=5)
        self.require(not (workflow / "corrupt-report").exists(), kind + ": invalid candidate produces no report directory")
        relocated = base / "relocated-offline-working-directory"
        relocated.mkdir()
        shutil.copy2(workflow / "mixed-run.json", relocated / "plan.json")
        shutil.copy2(workflow / "solved/result.json", relocated / "candidate.json")
        shutil.rmtree(workflow)
        self.require(not workflow.exists(), kind + ": original workflow directory removed before relocation checks")
        self.cli(python, env, relocated, kind + ": relocated offline check", "check", "plan.json", "candidate.json", offline=True)
        self.cli(python, env, relocated, kind + ": relocated offline report", "report", "plan.json", "candidate.json", "--out", "report", offline=True)
        self.cli(python, env, relocated, kind + ": relocated offline solve", "solve", "plan.json", "--out", "solved", offline=True)
        self.cli(python, env, relocated, kind + ": relocated offline new-result check", "check", "plan.json", "solved/result.json", offline=True)
        self.require(all(sha256(relocated / "report" / name) == digest for name, digest in report_digests.items()),
                     kind + ": relocated offline exports are byte-identical to original checked exports")

    def verify_source_archive(self, archive, python, env):
        source = extract_source(archive, self.work / "extracted-source")
        required = ["README.md", "LICENSE", "pyproject.toml", "tests/test_oracle.py", "tests/test_cli.py", "tests/test_contract.py"]
        required += [f"examples/{name}.json" for name in ("mixed-run", "pinned-run", "impossible")]
        required += [f"bench_window/data/{name}.json" for name in ("mixed-run", "pinned-run", "impossible")]
        self.require(all((source / name).is_file() for name in required), "Published source archive includes installation metadata, examples, installed data, and all acceptance test modules")
        docs = sorted(path.relative_to(source).as_posix() for path in (source / "docs").glob("*.md"))
        self.require(bool(docs), "Published source archive includes the supported documentation")
        tests = self.run("Source archive: extracted acceptance tests (source tests, not installed-package evidence)",
                         [str(python), "-m", "unittest", "discover", "-s", "tests", "-v"],
                         source, env, category="extracted_source_tests")
        count = re.search(r"Ran (\d+) tests?", tests.stderr + tests.stdout)
        self.require(bool(count) and int(count[1]) > 0, "Extracted source archive actually ran its acceptance tests")
        self.evidence["source_archive_tests"] = {"category": "extracted_source_tests", "test_methods": int(count[1]),
                                                  "passed": True, "documentation_files": docs,
                                                  "note": "Source tests import the extracted source. Separate isolated venv checks above exercise actual installed artifacts."}

    def verify(self):
        wheel, source = self.fetch_assets()
        self.verify_install("wheel", wheel)
        python, env, _ = self.verify_install("sdist", source)
        self.verify_source_archive(source, python, env)
        self.evidence.update(status="passed", verified_at=utc_now())

    def write_evidence(self):
        text = json.dumps(self.evidence, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        # Public evidence intentionally omits command output, private log contents,
        # environment values, executable paths, and absolute working directories.
        for private in sorted({str(self.work), str(CHECKOUT_ROOT), str(Path.home())}, key=len, reverse=True):
            if private and private != os.path.sep:
                text = text.replace(private, "<private-local-path>")
        self.args.output.parent.mkdir(parents=True, exist_ok=True)
        with self.args.output.open("x", encoding="utf-8") as output:
            output.write(text)


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--expected-source", required=True, help="exact full 40-character public release source commit")
    parser.add_argument("--work-dir", required=True, type=Path, help="new directory outside the development checkout")
    parser.add_argument("--output", required=True, type=Path, help="new JSON evidence file; no existing file is overwritten")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[0-9a-f]{40}", args.expected_source):
        parser.error("--expected-source must be an exact lowercase 40-character commit SHA")
    args.work_dir = args.work_dir.expanduser().resolve()
    args.output = args.output.expanduser().resolve()
    if within(args.work_dir, CHECKOUT_ROOT):
        parser.error("--work-dir must be outside the development checkout")
    if args.work_dir.exists():
        parser.error("--work-dir must be a new directory")
    if args.output.exists() or args.output.is_symlink():
        parser.error("--output must be a new file")
    return args


def main(argv=None):
    args = arguments(argv)
    args.work_dir.mkdir(parents=True, exist_ok=False)
    verifier = Verifier(args)
    try:
        verifier.verify()
    except (Exception, KeyboardInterrupt) as exc:
        verifier.evidence.update(status="failed", finished_at=utc_now(),
                                 failure={"type": type(exc).__name__, "message": str(exc)})
        verifier.write_evidence()
        print("Public release verification FAILED; partial JSON evidence and private diagnostic logs were retained.", file=sys.stderr)
        return 1
    verifier.write_evidence()
    print("Public release verification PASSED; JSON evidence records actual downloads and installed-artifact observations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
