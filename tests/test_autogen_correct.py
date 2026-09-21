"""One AutoGen agent preserves correct-then-continue. Optional extra, not a package."""

import importlib.util
import sys
from pathlib import Path

import pytest

from interrupthink import FakeLlm, JsonlLogger, Patch, ScriptedMonitor

REPO = Path(__file__).resolve().parents[1]
CASE = REPO / "cases" / "autogen-correct"


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
    pytest.importorskip("autogen")
    if str(CASE) not in sys.path:
        sys.path.insert(0, str(CASE))
    _purge_case_top_level_modules()
    return _load(CASE / "run.py", "autogen_correct_run")


def _config():
    if str(CASE) not in sys.path:
        sys.path.insert(0, str(CASE))
    return _load(CASE / "config.py", "autogen_correct_config")


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
    return ex.run_autogen_correct(
        interrupt=interrupt,
        sandbox=sandbox,
        llm=llm,
        monitor=monitor,
        logger=JsonlLogger(redact=False),
    )


def test_autogen_is_not_a_lock_dependency():
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    lock = (REPO / "uv.lock").read_text(encoding="utf-8")
    assert "autogen" not in pyproject.lower()
    assert 'name = "autogen"' not in lock
    assert 'name = "ag2"' not in lock


def test_interrupt_patch_writes_staging_not_production(tmp_path: Path):
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
    assert payload["request_count"] == 2
    assert payload["human_input_mode"] == "NEVER"
    assert "Wrote staging.txt" in (payload["committed_answer"] or "")
    assert payload["resume_modes"]
    assert all(mode == "rollback" for mode in payload["resume_modes"])
    prefix = payload["resume_prefix"] or ""
    assert cfg.STAGING_FACT in prefix
    assert "write the host file from the ticket" in prefix
    assert '<step kind="claim">the ticket host is production</step>' not in prefix
    assert payload["binding"] == cfg.STAGING_FACT


def test_without_interrupt_writes_production(tmp_path: Path):
    ex = _case()
    out = _scripted(ex, interrupt=False, sandbox=tmp_path)
    payload = ex.analyze(out)
    assert out.result.interrupt_ids == []
    assert payload["production_exists"] is True
    assert payload["staging_exists"] is False
    assert payload["written"] == ["production.txt"]
    assert (tmp_path / "production.txt").read_text(encoding="utf-8") == "deploy to production"
    assert payload["request_count"] == 1
    assert payload["resume_modes"] == []


def test_case_is_one_agent_not_pipe_or_userproxy(tmp_path: Path):
    pytest.importorskip("autogen")
    from autogen import ConversableAgent

    text = (CASE / "graph.py").read_text(encoding="utf-8")
    public = (REPO / "interrupthink" / "__init__.py").read_text(encoding="utf-8")
    pipe = (REPO / "cases" / "autogen-pipe" / "graph.py").read_text(encoding="utf-8")
    assert "from interrupthink import" in text
    assert "LiveOpenAILlm" in text
    assert "run_session" in text
    assert "ConversableAgent" in text
    assert 'human_input_mode="NEVER"' in text
    assert "UserProxyAgent(" not in text
    assert "initiate_chat(" not in text
    assert "initiate_chats(" not in text
    assert "GroupChat" not in text
    assert "write_agent" not in text
    assert "run_autogen_correct" not in public
    assert "run_autogen_pipe" in pipe
    ex = _case()
    out = _scripted(ex, interrupt=True, sandbox=tmp_path)
    assert isinstance(out.agent, ConversableAgent)
    assert out.agent.human_input_mode == "NEVER"


def test_example_calls_interruptible_not_the_case():
    example = (REPO / "examples" / "autogen_correct.py").read_text(encoding="utf-8")
    run = (CASE / "run.py").read_text(encoding="utf-8")
    graph = (CASE / "graph.py").read_text(encoding="utf-8")
    readme = (CASE / "README.md").read_text(encoding="utf-8")
    assert "from interrupthink import" in example
    assert "LiveOpenAILlm" in example
    assert "run_session" in example
    assert "ConversableAgent" in example
    assert 'human_input_mode="NEVER"' in example
    assert "UserProxyAgent(" not in example
    assert "initiate_chat(" not in example
    assert "GroupChat" not in example
    assert "importlib" not in example
    assert "spec_from_file_location" not in example
    assert "run_autogen_correct" not in example
    assert "FakeLlm" not in example
    for text in (graph, run, readme):
        assert "FakeLlm" not in text
        assert "ScriptedMonitor" not in text
    assert "CORRECTED_THEN_WRITE" in (CASE / "config.py").read_text(encoding="utf-8")
