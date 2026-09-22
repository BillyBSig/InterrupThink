"""run_session in one LangGraph node; tools node is backup. Optional extra, not a package."""

import importlib.util
from pathlib import Path

import pytest

from interrupthink import FakeLlm, ScriptedMonitor

REPO = Path(__file__).resolve().parents[1]


def _case():
    path = REPO / "cases" / "langgraph-node" / "run.py"
    spec = importlib.util.spec_from_file_location("langgraph_node_run", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _wired(ex, *, interrupt: bool, sandbox: Path):
    if interrupt:
        llm = FakeLlm([ex.WRITE_WRONG, ex.WRITE_STOPPED])
        monitor = ScriptedMonitor(
            trigger_kind="premise",
            trigger_contains="the code freeze is over",
        )
    else:
        llm = FakeLlm([ex.WRITE_WRONG])
        monitor = ScriptedMonitor(trigger_kind=None)
    return ex.run_langgraph_specialist(
        interrupt=interrupt, sandbox=sandbox, llm=llm, monitor=monitor
    )


def test_langgraph_is_not_a_lock_dependency():
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    lock = (REPO / "uv.lock").read_text(encoding="utf-8")
    assert "langgraph" not in pyproject
    assert "langchain" not in pyproject
    assert "langchain-openai" not in pyproject
    assert "name = \"langgraph\"" not in lock
    assert "name = \"langchain\"" not in lock


def test_interrupt_skips_tools_node(tmp_path: Path):
    pytest.importorskip("langgraph")
    ex = _case()
    out = _wired(ex, interrupt=True, sandbox=tmp_path)
    payload = ex.analyze(out)
    assert out.result.interrupt_ids
    assert payload["tool_node_visits"] == 0
    assert payload["tool_calls"] == []
    assert payload["hotfix_exists"] is False
    assert not (tmp_path / "hotfix.txt").exists()
    assert "tool.execute" not in payload["event_sequence"]
    assert "Did not write" in (payload["committed_answer"] or "")


def test_without_interrupt_tools_node_writes_hotfix(tmp_path: Path):
    pytest.importorskip("langgraph")
    ex = _case()
    out = _wired(ex, interrupt=False, sandbox=tmp_path)
    payload = ex.analyze(out)
    assert out.result.interrupt_ids == []
    assert payload["tool_node_visits"] == 1
    assert payload["hotfix_exists"] is True
    assert payload["written"] == ["hotfix.txt"]
    assert payload["tool_calls"] == [
        {"name": "write", "args": {"path": "hotfix.txt", "content": "hotfix for main"}}
    ]
    assert (tmp_path / "hotfix.txt").read_text(encoding="utf-8") == "hotfix for main"


def test_case_is_one_node_not_a_framework_package():
    text = (REPO / "cases" / "langgraph-node" / "run.py").read_text(encoding="utf-8")
    public = (REPO / "interrupthink" / "__init__.py").read_text(encoding="utf-8")
    assert "LiveLlm" in text
    assert "execute_tools_when_ok=False" in text
    assert 'add_node("specialist"' in text
    assert 'add_node("tools"' in text
    assert "import langchain" not in text
    assert "from langchain" not in text
    assert "langchain_openai" not in text
    assert "MemorySaver" not in text
    assert "from langgraph.checkpoint" not in text
    assert "run_langgraph_specialist" not in public


def test_example_calls_interruptible_not_the_case():
    example = (REPO / "examples" / "langgraph_specialist_node.py").read_text(encoding="utf-8")
    assert "from interrupthink import" in example
    assert "LiveLlm" in example
    assert "run_session" in example
    assert "from langgraph.graph import" in example
    assert "importlib" not in example
    assert "spec_from_file_location" not in example
    assert "FakeLlm" not in example
    assert "run_langgraph_specialist" not in example
