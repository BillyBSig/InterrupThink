"""run_session inside a LangChain specialist. Optional extra, not a package."""

import importlib.util
import sys
from pathlib import Path

import pytest

from interrupthink import FakeLlm, ScriptedMonitor

REPO = Path(__file__).resolve().parents[1]
CASE = REPO / "cases" / "langchain-specialist"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _purge_case_top_level_modules() -> None:
    """Cookbooks import bare `config`/`tools`; drop cached modules from other cases."""
    for name in ("config", "tools", "agents", "chat", "run"):
        sys.modules.pop(name, None)


def _case():
    if str(CASE) not in sys.path:
        sys.path.insert(0, str(CASE))
    _purge_case_top_level_modules()
    return _load(CASE / "run.py", "langchain_specialist_run")


def _config():
    if str(CASE) not in sys.path:
        sys.path.insert(0, str(CASE))
    return _load(CASE / "config.py", "langchain_specialist_config")


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
    return ex.create_specialist(
        interrupt=interrupt,
        sandbox=sandbox,
        llm=llm,
        monitor=monitor,
    )


def test_langchain_is_not_a_lock_dependency():
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    lock = (REPO / "uv.lock").read_text(encoding="utf-8")
    assert "langchain" not in pyproject
    assert "langchain-openai" not in pyproject
    assert "langchain_core" not in pyproject
    assert "name = \"langchain\"" not in lock
    assert "name = \"langchain-core\"" not in lock
    assert "name = \"langchain-openai\"" not in lock


def test_interrupt_skips_sandbox_write(tmp_path: Path):
    pytest.importorskip("langchain_core")
    ex = _case()
    specialist = _scripted(ex, interrupt=True, sandbox=tmp_path)
    payload = ex.analyze(specialist.run())
    assert payload["interrupt_ids"]
    assert payload["tool_calls"] == []
    assert payload["hotfix_exists"] is False
    assert not (tmp_path / "hotfix.txt").exists()
    assert "tool.execute" not in payload["event_sequence"]
    assert "Did not write" in (payload["committed_answer"] or "")
    assert payload["lc_tool_name"] == "write"


def test_without_interrupt_wrapper_writes_hotfix(tmp_path: Path):
    pytest.importorskip("langchain_core")
    ex = _case()
    specialist = _scripted(ex, interrupt=False, sandbox=tmp_path)
    payload = ex.analyze(specialist.run())
    assert payload["interrupt_ids"] == []
    assert payload["hotfix_exists"] is True
    assert payload["written"] == ["hotfix.txt"]
    assert payload["tool_calls"] == [
        {"name": "write", "args": {"path": "hotfix.txt", "content": "hotfix for main"}}
    ]
    assert (tmp_path / "hotfix.txt").read_text(encoding="utf-8") == "hotfix for main"


def test_runnable_invoke_matches_run(tmp_path: Path):
    pytest.importorskip("langchain_core")
    ex = _case()
    specialist = _scripted(ex, interrupt=False, sandbox=tmp_path)
    via_chain = specialist.as_runnable().invoke("write the hotfix")
    assert via_chain["hotfix_exists"] is True
    assert via_chain["lc_tool_name"] == "write"


def test_cookbook_does_not_present_fake_llm():
    agents = (CASE / "agents.py").read_text(encoding="utf-8")
    run = (CASE / "run.py").read_text(encoding="utf-8")
    readme = (CASE / "README.md").read_text(encoding="utf-8")
    example = (REPO / "examples" / "langchain_specialist.py").read_text(encoding="utf-8")
    tools = (CASE / "tools.py").read_text(encoding="utf-8")
    public = (REPO / "src" / "interrupthink" / "__init__.py").read_text(encoding="utf-8")
    for text in (agents, run, readme):
        assert "FakeLlm" not in text
        assert "ScriptedMonitor" not in text
        assert "--mock" not in text
    assert "from interrupthink import" in example
    assert "LiveLlm" in example
    assert "run_session" in example
    assert "importlib" not in example
    assert "spec_from_file_location" not in example
    assert "create_specialist" not in example
    assert "FakeLlm" not in example
    assert "LiveLlm" in agents
    assert "LlmMonitor" in agents
    assert "from interrupthink import" in agents
    assert "def create_specialist(" in agents
    assert "ChatPromptTemplate" in agents
    assert "class WriteHotfixTool" in tools
    assert "create_specialist" not in public
    assert "interruptible-langchain" not in agents
    assert "from langgraph" not in agents
    assert "AgentExecutor(" not in agents
