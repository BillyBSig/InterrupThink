"""LangChain wrapper preserves correct-then-continue. Optional extra, not a package."""

import importlib.util
import sys
from pathlib import Path

import pytest

from interrupthink import FakeLlm, JsonlLogger, Patch, ScriptedMonitor

REPO = Path(__file__).resolve().parents[1]
CASE = REPO / "cases" / "langchain-correct"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _purge_case_top_level_modules() -> None:
    for name in ("config", "tools", "agents", "chat", "run"):
        sys.modules.pop(name, None)


def _case():
    if str(CASE) not in sys.path:
        sys.path.insert(0, str(CASE))
    _purge_case_top_level_modules()
    return _load(CASE / "run.py", "langchain_correct_run")


def _config():
    if str(CASE) not in sys.path:
        sys.path.insert(0, str(CASE))
    return _load(CASE / "config.py", "langchain_correct_config")


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
    return ex.create_specialist(
        interrupt=interrupt,
        sandbox=sandbox,
        llm=llm,
        monitor=monitor,
        logger=JsonlLogger(redact=False),
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


def test_interrupt_patch_writes_staging_not_production(tmp_path: Path):
    pytest.importorskip("langchain_core")
    ex = _case()
    cfg = _config()
    specialist = _scripted(ex, interrupt=True, sandbox=tmp_path)
    payload = ex.analyze(specialist.run())
    assert payload["interrupt_ids"]
    assert payload["production_exists"] is False
    assert not (tmp_path / "production.txt").exists()
    assert "production.txt" not in payload["written"]
    assert payload["staging_exists"] is True
    assert payload["written"] == ["staging.txt"]
    assert payload["request_count"] == 2
    assert "Wrote staging.txt" in (payload["committed_answer"] or "")
    assert "Wrote production.txt" not in (payload["committed_answer"] or "")
    assert payload["lc_tool_name"] == "write"
    assert payload["resume_modes"]
    assert all(mode == "rollback" for mode in payload["resume_modes"])
    prefix = payload["resume_prefix"] or ""
    assert cfg.STAGING_FACT in prefix
    assert "write the host file from the ticket" in prefix
    assert '<step kind="claim">the ticket host is production</step>' not in prefix
    assert payload["binding"] == cfg.STAGING_FACT


def test_without_interrupt_writes_production(tmp_path: Path):
    pytest.importorskip("langchain_core")
    ex = _case()
    specialist = _scripted(ex, interrupt=False, sandbox=tmp_path)
    payload = ex.analyze(specialist.run())
    assert payload["interrupt_ids"] == []
    assert payload["production_exists"] is True
    assert payload["staging_exists"] is False
    assert payload["written"] == ["production.txt"]
    assert (tmp_path / "production.txt").read_text(encoding="utf-8") == "deploy to production"
    assert payload["request_count"] == 1
    assert payload["resume_modes"] == []


def test_runnable_invoke_matches_run(tmp_path: Path):
    pytest.importorskip("langchain_core")
    ex = _case()
    specialist = _scripted(ex, interrupt=True, sandbox=tmp_path)
    via_chain = specialist.as_runnable().invoke("write the host file")
    assert via_chain["staging_exists"] is True
    assert via_chain["production_exists"] is False
    assert via_chain["lc_tool_name"] == "write"


def test_cookbook_does_not_present_fake_llm():
    agents = (CASE / "agents.py").read_text(encoding="utf-8")
    run = (CASE / "run.py").read_text(encoding="utf-8")
    readme = (CASE / "README.md").read_text(encoding="utf-8")
    example = (REPO / "examples" / "langchain_correct.py").read_text(encoding="utf-8")
    tools = (CASE / "tools.py").read_text(encoding="utf-8")
    public = (REPO / "interrupthink" / "__init__.py").read_text(encoding="utf-8")
    specialist_agents = (REPO / "cases" / "langchain-specialist" / "agents.py").read_text(
        encoding="utf-8"
    )
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
    assert "class WriteHostTool" in tools
    assert "create_specialist" not in public
    assert "interruptible-langchain" not in agents
    assert "interrupthink-langchain" not in agents
    assert "from langgraph" not in agents
    assert "AgentExecutor(" not in agents
    assert "CORRECTED_THEN_WRITE" in (CASE / "config.py").read_text(encoding="utf-8")
    assert "hotfix.txt" not in agents
    assert "freeze is over" not in agents
    assert "def freeze_monitor" in specialist_agents
    assert "def host_monitor" in agents
