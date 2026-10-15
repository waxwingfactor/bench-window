"""CI: isolated wheel/sdist installations, plus exact source/build metadata."""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import subprocess
import sys
import tempfile
import tarfile
import venv

root = Path(__file__).resolve().parents[1]
dist = root / "dist"
artifacts = sorted(dist.glob("*.whl")) + sorted(dist.glob("*.tar.gz"))
assert len(artifacts) == 2, artifacts
clean_env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONHOME"}}
clean_env["PYTHONNOUSERSITE"] = "1"
for artifact in artifacts:
    with tempfile.TemporaryDirectory(prefix="bench-window-dist-") as temp:
        base = Path(temp)
        venv.create(base / "env", with_pip=True)
        python = base / "env" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        def run(*args, expected=0):
            call = subprocess.run([str(python), *args], cwd=base, env=clean_env,
                                  text=True, capture_output=True)
            if call.returncode != expected:
                raise RuntimeError(f"{args}: {call.returncode}\n{call.stdout}\n{call.stderr}")
        run("-m", "pip", "install", "--no-deps", str(artifact))
        run("-I", "-m", "bench_window", "example", "--out", "plan.json")
        run("-I", "-m", "bench_window", "solve", "plan.json", "--out", "run")
        run("-I", "-m", "bench_window", "check", "plan.json", "run/result.json")
        run("-I", "-m", "bench_window", "example", "--name", "pinned-run", "--out", "pinned.json")
        run("-I", "-m", "bench_window", "solve", "pinned.json", "--out", "remaining")
        run("-I", "-m", "bench_window", "example", "--name", "impossible", "--out", "bad.json")
        run("-I", "-m", "bench_window", "solve", "bad.json", "--out", "bad", expected=3)
        assert sorted(p.name for p in (base / "bad").iterdir()) == ["result.json"]
# A source installation alone cannot prove examples/docs/tests were shipped.
with tempfile.TemporaryDirectory(prefix="bench-window-source-") as temp:
    base = Path(temp)
    with tarfile.open(next(dist.glob("*.tar.gz")), "r:gz") as archive:
        members = archive.getmembers()
        for member in members:
            path = PurePosixPath(member.name)
            assert not path.is_absolute() and ".." not in path.parts
            assert member.isfile() or member.isdir(), "links/special files not expected"
        prefixes = {PurePosixPath(m.name).parts[0] for m in members}
        assert len(prefixes) == 1
        prefix = prefixes.pop()
        names = {str(PurePosixPath(m.name).relative_to(prefix)) for m in members}
        required = {"README.md", "LICENSE", "pyproject.toml", "docs/guide.md",
                    "docs/architecture.md", "docs/research.md", "docs/review.md",
                    "examples/mixed-run.json", "examples/pinned-run.json", "examples/impossible.json",
                    "tests/test_oracle.py", "tests/test_cli.py", "tests/test_contract.py",
                    "scripts/check_distribution.py"}
        assert required <= names, "missing sdist files: " + str(sorted(required - names))
        archive.extractall(base)
    test = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                          cwd=base / prefix, env=clean_env, text=True, capture_output=True)
    if test.returncode:
        raise RuntimeError("extracted sdist tests failed\n" + test.stdout + test.stderr)
    print("Source archive includes required docs/examples/tests; extracted suite passed.")
checksums = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts}
(dist / "SHA256SUMS").write_text("".join(f"{digest}  {name}\n" for name, digest in checksums.items()), encoding="utf-8")
revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
(dist / "build-info.json").write_text(json.dumps({"source_revision": revision,
    "python": platform.python_version(), "system": platform.system(), "artifacts": checksums,
    "workflow": "CI / Distribution", "run_id": os.environ.get("GITHUB_RUN_ID"),
    "installation_checks": "wheel and sdist installed separately in fresh venvs outside checkout; installed examples, feasible/check, pinned replan, infeasible; required source contents checked and extracted suite passed"}, indent=2) + "\n", encoding="utf-8")
print("Both distributions installed and exercised outside the checkout.")
