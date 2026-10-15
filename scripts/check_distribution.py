"""CI: isolated wheel/sdist installations, plus exact source/build metadata."""

import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
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
checksums = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts}
(dist / "SHA256SUMS").write_text("".join(f"{digest}  {name}\n" for name, digest in checksums.items()), encoding="utf-8")
revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
(dist / "build-info.json").write_text(json.dumps({"source_revision": revision,
    "python": platform.python_version(), "system": platform.system(), "artifacts": checksums,
    "workflow": "CI / Distribution", "run_id": os.environ.get("GITHUB_RUN_ID"),
    "installation_checks": "wheel and sdist installed separately in fresh venvs outside checkout; installed examples, feasible/check, pinned replan, infeasible"}, indent=2) + "\n", encoding="utf-8")
print("Both distributions installed and exercised outside the checkout.")
