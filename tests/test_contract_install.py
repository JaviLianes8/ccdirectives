"""The installed command: `python -m ccdirectives` runs and the console script is declared."""

from __future__ import annotations

import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import ccdirectives

_SRC = Path(__file__).resolve().parents[1] / "src"


def test_python_dash_m_runs_the_command() -> None:
    env = dict(os.environ)
    if _SRC.is_dir():
        env["PYTHONPATH"] = os.pathsep.join([str(_SRC), env.get("PYTHONPATH", "")])
    done = subprocess.run(
        [sys.executable, "-m", "ccdirectives", "max-age=60, x-a"],
        capture_output=True,
        env=env,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    report = json.loads(done.stdout)
    assert report["directives"] == {"max-age": 60, "x-a": True}
    assert report["extensions"] == ["x-a"] and report["lifetime"] == 60


def test_the_console_script_is_declared_and_installed() -> None:
    try:
        distribution = importlib.metadata.distribution("ccdirectives")
    except importlib.metadata.PackageNotFoundError:
        pytest.skip("ccdirectives is not installed in this environment")
    scripts = [e for e in distribution.entry_points if e.group == "console_scripts"]
    assert [(e.name, e.value) for e in scripts] == [("ccdirectives", "ccdirectives._cli:main")]
    assert distribution.version == ccdirectives.__version__
    found = shutil.which("ccdirectives", path=str(Path(sys.executable).parent))
    assert found is not None, "the console script is missing from the environment"
    done = subprocess.run([found, "--age", "30", "max-age=60"], capture_output=True, check=False)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["fresh"] is True
