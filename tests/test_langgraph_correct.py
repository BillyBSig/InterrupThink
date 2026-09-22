"""LangGraph agent + ToolNode preserves correct-then-continue. Optional extra, not a package."""

import importlib.util
import sys
from pathlib import Path

import pytest

from interrupthink import FakeLlm, JsonlLogger, Patch, ScriptedMonitor

REPO = Path(__file__).resolve().parents[1]
CASE = REPO / "cases" / "langgraph-correct"


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
    return _load(CASE / "run.py", "langgraph_correct_run")


def _config():
    if str(CASE) not in sys.path:
        sys.path.insert(0, str(CASE))
    return _load(CASE / "config.py", "langgraph_correct_config")


def _scripted(ex, *, interrupt: bool, sandbox: Path):
    cfg = _config()
    if interrupt:
        llm = FakeLlm([cfg.WRONG_THEN_WRITE, cfg.CORRECTED_THEN_WRITE])
        monitor = ScriptedMonitor(
            trigger_kind="claim",
            trigger_contains=cfg.WRONG_HOST,
            patch=Patch(
                from_agent="A",
                target_unit_id="",
                rollback_to=None,
                diagnosis="ticket host is staging this week, not production",
                missing=cfg.STAGING_FACT,
                directive="do not write as production; continue with staging",
                preserve=[],
            ),
        )
    else:
        llm = FakeLlm([cfg.WRONG_THEN_WRITE])
        monitor = ScriptedMonitor(trigger_kind=None)
    return ex.run_correct(
        interrupt=interrupt,
        sandbox=sandbox,
        llm=llm,
        monitor=monitor,
        logger=JsonlLogger(redact=False),
    )


def test_langgraph_is_not_a_lock_dependency():
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    lock = (REPO / "uv.lock").read_text(encoding="utf-8")
    assert "langgraph" not in pyproject
    assert "langchain" not in pyproject
    assert "name = \"langgraph\"" not in lock
    assert "name = \"langchain\"" not in lock


def test_interrupt_patch_toolnode_writes_staging_not_production(tmp_path: Path):
    pytest.importorskip("langgraph")
    pytest.importorskip("langchain_core")
    ex = _case()
    cfg = _config()
    out = _scripted(ex, interrupt=True, sandbox=tmp_path)
    payload = ex.analyze(out)
    assert out.result.interrupt_ids
    assert payload["production_exists"] is False
    assert not (tmp_path / "production.txt").exists()
    assert "production.txt" not in payload["written"]
    assert payload["staging_exists"] is True
    assert payload["written"] == ["staging.txt"]
    assert payload["tool_node_visits"] == 1
    assert payload["request_count"] == 2
    assert "Wrote staging.txt" in (payload["committed_answer"] or "")
    assert payload["lc_tool_name"] == "write"
    assert payload["resume_modes"]
    assert all(mode == "rollback" for mode in payload["resume_modes"])
    prefix = payload["resume_prefix"] or ""
    assert cfg.STAGING_FACT in prefix
    assert "write the host file from the ticket" in prefix
    assert '<step kind="claim">the ticket host is production</step>' not in prefix
    assert payload["binding"] == cfg.STAGING_FACT


def test_without_interrupt_toolnode_writes_production(tmp_path: Path):
    pytest.importorskip("langgraph")
    pytest.importorskip("langchain_core")
    ex = _case()
    out = _scripted(ex, interrupt=False, sandbox=tmp_path)
    payload = ex.analyze(out)
    assert out.result.interrupt_ids == []
    assert payload["tool_node_visits"] == 1
    assert payload["production_exists"] is True
    assert payload["staging_exists"] is False
    assert payload["written"] == ["production.txt"]
    assert (tmp_path / "production.txt").read_text(encoding="utf-8") == "deploy to production"
    assert payload["request_count"] == 1
    assert payload["resume_modes"] == []


def test_case_uses_official_tool_node_and_is_not_freeze_hold():
    text = (CASE / "graph.py").read_text(encoding="utf-8")
    public = (REPO / "interrupthink" / "__init__.py").read_text(encoding="utf-8")
    apply_graph = (REPO / "cases" / "langgraph-apply" / "graph.py").read_text(encoding="utf-8")
    assert "from interrupthink import" in text
    assert "execute_tools_when_ok=False" in text
    assert 'add_node("agent"' in text
    assert "from langgraph.prebuilt import ToolNode" in text
    assert "ToolNode(" in text
    assert "make_agent_node" in text
    assert "blocked = bool(result.interrupt_ids)" not in text
    assert "hotfix.txt" not in text
    assert "CORRECTED_THEN_WRITE" in (CASE / "config.py").read_text(encoding="utf-8")
    assert "run_langgraph_specialist" not in text
    assert "run_correct" not in public
    assert "create_correct_graph" not in public
    assert "MemorySaver" not in text
    assert "from langgraph.checkpoint" not in text
    assert "interrupthink-langgraph" not in text
    assert "blocked = bool(result.interrupt_ids)" in apply_graph


def test_example_calls_interruptible_not_the_case():
    example = (REPO / "examples" / "langgraph_correct.py").read_text(encoding="utf-8")
    assert "from interrupthink import" in example
    assert "LiveLlm" in example
    assert "run_session" in example
    assert "from langgraph.prebuilt import ToolNode" in example
    assert "importlib" not in example
    assert "spec_from_file_location" not in example
    assert "FakeLlm" not in example
    assert "run_correct" not in example
    assert "hotfix.txt" not in example
    agents = (CASE / "graph.py").read_text(encoding="utf-8")
    run = (CASE / "run.py").read_text(encoding="utf-8")
    readme = (CASE / "README.md").read_text(encoding="utf-8")
    for text in (agents, run, readme):
        assert "FakeLlm" not in text
        assert "ScriptedMonitor" not in text
