"""Local wheel install (not PyPI). Dummy run_session. No API key."""

import os
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
UV = shutil.which("uv")
assert UV, "uv required to build a local wheel without PyPI"

SCRIPT = r"""
from interrupthink import DummyTool, FakeLlm, ScriptedMonitor, run_session

wrong = '''
<step kind="plan">publish the changelog now</step>
<step kind="premise">the changelog is already approved</step>
<step kind="tool_intent" reversible="false">{"name":"publish","args":{"doc":"changelog"}}</step>
<answer>Published the changelog.</answer>
'''
stopped = '''
<step kind="claim">changelog is not approved; do not publish</step>
<answer>Did not publish.</answer>
'''
tool = DummyTool()
llm = FakeLlm([wrong, stopped])
monitor = ScriptedMonitor(trigger_kind="premise", trigger_contains="already approved")
result = run_session(llm=llm, monitor=monitor, tool=tool)
assert result.interrupt_ids
assert tool.calls == []
print("ok", result.committed_answer)
"""


def _clean_env():
    env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "VIRTUAL_ENV", "PYTHONHOME"}}
    env["PYTHONPATH"] = ""
    env["UV_NO_INDEX"] = "1"
    env["UV_OFFLINE"] = "1"
    return env


def test_local_wheel_run_session_without_pypi(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    env = _clean_env()
    try:
        subprocess.run(
            [UV, "build", "--wheel", "-o", str(dist), str(REPO)],
            cwd=tmp_path,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        wheels = list(dist.glob("interrupthink-*.whl"))
        assert wheels, list(dist.iterdir())
        venv = tmp_path / "venv"
        subprocess.run([UV, "venv", str(venv)], cwd=tmp_path, env=env, check=True, capture_output=True, text=True)
        py = venv / "bin" / "python"
        subprocess.run(
            [UV, "pip", "install", "--python", str(py), "--offline", "--no-index", str(wheels[0])],
            cwd=tmp_path,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        cwd = tmp_path / "stranger"
        cwd.mkdir()
        completed = subprocess.run(
            [str(py), "-c", SCRIPT],
            cwd=cwd,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        assert completed.stdout.startswith("ok")
        assert "PyPI" not in completed.stdout
    finally:
        shutil.rmtree(REPO / "build", ignore_errors=True)
        shutil.rmtree(REPO / "interrupthink.egg-info", ignore_errors=True)
        shutil.rmtree(REPO / "interruptible_team_reasoning.egg-info", ignore_errors=True)
