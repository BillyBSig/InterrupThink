"""Host tool-gate never sees a push when the freeze premise is cut. No LangGraph. No git."""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _example():
    path = REPO / "examples" / "dummy" / "host_loop_dummy.py"
    spec = importlib.util.spec_from_file_location("host_loop_dummy", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_interrupt_skips_host_gate_and_dummy_push():
    result, tool, host = _example().run_host_loop(interrupt=True)
    assert host.approvals == []
    assert tool.calls == []
    assert result.interrupt_ids
    assert result.committed_answer == "Did not push. Freeze still holds."


def test_without_interrupt_host_approves_then_dummy_push():
    result, tool, host = _example().run_host_loop(interrupt=False)
    push = {"name": "push", "args": {"remote": "origin", "branch": "main"}}
    assert result.interrupt_ids == []
    assert host.approvals == [push]
    assert tool.calls == [push]
    assert result.committed_answer == "Pushed hotfix to origin/main."


def test_example_is_library_host_not_framework():
    text = (REPO / "examples" / "dummy" / "host_loop_dummy.py").read_text(encoding="utf-8")
    assert "from src." not in text
    assert "import langgraph" not in text
    assert "from langgraph" not in text
    assert "import langchain" not in text
    assert "from langchain" not in text
    assert "subprocess" not in text
    assert "git " not in text
    assert "OPENAI" not in text
    assert "from interrupthink import DummyTool, FakeLlm, ScriptedMonitor, run_session" in text
