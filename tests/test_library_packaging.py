"""Stranger surface: public core import, no src.* in the example."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from interrupthink import LlmMonitor, ThoughtUnit, run_session


REPO = Path(__file__).resolve().parents[1]


def test_public_core_symbols_are_importable():
    assert run_session
    assert ThoughtUnit
    assert LlmMonitor


def test_example_does_not_import_src():
    text = (REPO / "examples" / "dummy" / "staging_migrate.py").read_text(encoding="utf-8")
    assert "from src." not in text
    assert "PYTHONPATH" not in text
    assert "from staging_case import" in text
    assert "run_staging_case" in text


def test_import_from_other_cwd_without_pythonpath(tmp_path):
    venv = tmp_path / "venv"
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONPATH"] = ""
    py = _install_editable(venv, env)
    cwd = tmp_path / "stranger"
    cwd.mkdir()
    script = (
        "from interrupthink import LlmMonitor, ThoughtUnit, run_session\n"
        "assert run_session and ThoughtUnit and LlmMonitor\n"
    )
    subprocess.run(
        [str(py), "-c", script],
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _install_editable(venv: Path, env: dict[str, str]) -> Path:
    uv = shutil.which("uv")
    if uv:
        subprocess.run(
            [uv, "venv", str(venv)],
            cwd=REPO,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        py = venv / "bin" / "python"
        subprocess.run(
            [uv, "pip", "install", "--python", str(py), "-e", str(REPO)],
            cwd=REPO,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        return py
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv)],
        cwd=REPO,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    py = venv / "bin" / "python"
    subprocess.run(
        [str(py), "-m", "pip", "install", "-e", str(REPO)],
        cwd=REPO,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return py
