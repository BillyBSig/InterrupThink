"""Fill the LangGraph agent node; official ToolNode is backup. Optional extra, not a package."""

import importlib.util
import sys
from pathlib import Path

import pytest

from interrupthink import FakeLlm, ScriptedMonitor

REPO = Path(__file__).resolve().parents[1]
CASE = REPO / "cases" / "langgraph-apply"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _purge_case_top_level_modules() -> None:
    for name in ("config", "tools", "graph", "run", "agents", "chat"):
        sys.modules.pop(name, None)


def _case():
    if str(CASE) not in sys.path:
        sys.path.insert(0, str(CASE))
    _purge_case_top_level_modules()
    return _load(CASE / "run.py", "langgraph_apply_run")


def _config():
    if str(CASE) not in sys.path:
        sys.path.insert(0, str(CASE))
    return _load(CASE / "config.py", "langgraph_apply_config")


def _scripted(ex, *, interrupt: bool, sandbox: Path):
    cfg = _config()
    if interrupt:
        llm = FakeLlm([cfg.WRITE_WRONG, cfg.WRITE_STOPPED])
        monitor = ScriptedMonitor(
            trigger_kind="premise",
            trigger_contains="code freeze is over",
        )
    else:
        llm = FakeLlm([cfg.WRITE_WRONG])
        monitor = ScriptedMonitor(trigger_kind=None)
    return ex.run_apply(interrupt=interrupt, sandbox=sandbox, llm=llm, monitor=monitor)


def test_langgraph_is_not_a_lock_dependency():
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    lock = (REPO / "uv.lock").read_text(encoding="utf-8")
    assert "langgraph" not in pyproject
    assert "langchain" not in pyproject
    assert "name = \"langgraph\"" not in lock
    assert "name = \"langchain\"" not in lock


def test_interrupt_skips_tool_node(tmp_path: Path):
    pytest.importorskip("langgraph")
    pytest.importorskip("langchain_core")
    ex = _case()
    out = _scripted(ex, interrupt=True, sandbox=tmp_path)
    payload = ex.analyze(out)
    assert out.result.interrupt_ids
    assert payload["tool_node_visits"] == 0
    assert payload["tool_calls"] == []
    assert payload["hotfix_exists"] is False
    assert not (tmp_path / "hotfix.txt").exists()
    assert "tool.execute" not in payload["event_sequence"]
    assert "Did not write" in (payload["committed_answer"] or "")
    assert payload["lc_tool_name"] == "write"


def test_without_interrupt_tool_node_writes_hotfix(tmp_path: Path):
    pytest.importorskip("langgraph")
    pytest.importorskip("langchain_core")
    ex = _case()
    out = _scripted(ex, interrupt=False, sandbox=tmp_path)
    payload = ex.analyze(out)
    assert out.result.interrupt_ids == []
    assert payload["tool_node_visits"] == 1
    assert payload["hotfix_exists"] is True
    assert payload["written"] == ["hotfix.txt"]
    assert payload["tool_calls"] == [
        {"name": "write", "args": {"path": "hotfix.txt", "content": "hotfix for main"}}
    ]
    assert (tmp_path / "hotfix.txt").read_text(encoding="utf-8") == "hotfix for main"


def test_case_uses_official_tool_node_not_host_copy():
    text = (CASE / "graph.py").read_text(encoding="utf-8")
    public = (REPO / "interrupthink" / "__init__.py").read_text(encoding="utf-8")
    host = (REPO / "cases" / "langgraph-node" / "run.py").read_text(encoding="utf-8")
    assert "from interrupthink import" in text
    assert "execute_tools_when_ok=False" in text
    assert 'add_node("agent"' in text
    assert "from langgraph.prebuilt import ToolNode" in text
    assert "ToolNode(" in text
    assert "make_agent_node" in text
    assert "run_langgraph_specialist" not in text
    assert "from langgraph.prebuilt import ToolNode" not in host
    assert "run_apply" not in public
    assert "create_apply_graph" not in public
    assert "MemorySaver" not in text
    assert "from langgraph.checkpoint" not in text


def test_example_calls_interruptible_not_the_case():
    example = (REPO / "examples" / "langgraph_apply.py").read_text(encoding="utf-8")
    assert "from interrupthink import" in example
    assert "LiveOpenAILlm" in example
    assert "run_session" in example
    assert "from langgraph.prebuilt import ToolNode" in example
    assert "importlib" not in example
    assert "spec_from_file_location" not in example
    assert "FakeLlm" not in example
    assert "run_apply" not in example
    assert "langgraph-apply" not in example or "cases/langgraph-apply" in example
