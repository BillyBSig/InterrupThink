"""Two CrewAI roles, each run_session, one supervisor. Optional extra, not a package."""

import importlib.util
import sys
from pathlib import Path

import pytest

from interrupthink import FakeLlm, ScriptedMonitor

REPO = Path(__file__).resolve().parents[1]
CASE = REPO / "cases" / "crewai-pipe"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _purge_case_top_level_modules() -> None:
    for name in ("config", "tools", "graph", "run"):
        sys.modules.pop(name, None)


def _case():
    pytest.importorskip("crewai")
    if str(CASE) not in sys.path:
        sys.path.insert(0, str(CASE))
    _purge_case_top_level_modules()
    return _load(CASE / "run.py", "crewai_pipe_run")


def _wired(ex, *, interrupt_stale: bool, sandbox: Path):
    monitor = ScriptedMonitor(
        trigger_kind="premise",
        trigger_contains="stale policy is in force",
    )
    if interrupt_stale:
        retrieve_llm = FakeLlm([ex.RETRIEVE_STALE, ex.RETRIEVE_STOPPED])
        write_llm = None
    else:
        retrieve_llm = FakeLlm([ex.RETRIEVE_CURRENT])
        fixtures = CASE.parent / "two-specialists" / "fixtures" / "policy"
        forwarded = (fixtures / "current.txt").read_text(encoding="utf-8")
        write_llm = FakeLlm([ex._write_xml(forwarded)])
    return ex.run_crewai_pipe(
        interrupt_stale=interrupt_stale,
        sandbox=sandbox,
        retrieve_llm=retrieve_llm,
        write_llm=write_llm,
        monitor=monitor,
    )


def test_crewai_is_not_a_lock_dependency():
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    lock = (REPO / "uv.lock").read_text(encoding="utf-8")
    assert "crewai" not in pyproject.lower()
    assert 'name = "crewai"' not in lock


def test_stale_claim_does_not_write_decision(tmp_path: Path):
    ex = _case()
    out = _wired(ex, interrupt_stale=True, sandbox=tmp_path)
    payload = ex.analyze(out)
    assert payload["decision_exists"] is False
    assert payload["write_calls"] == []
    assert out.write_result is None
    assert payload["session_count"] == 1
    assert payload["write_role_visits"] == 0
    assert out.retrieve_result.interrupt_ids
    assert payload["retrieve_calls"] == [
        {"name": "retrieve", "args": {"path": "stale.txt"}}
    ]
    assert not (tmp_path / "decision.txt").exists()


def test_current_policy_writes_one_decision(tmp_path: Path):
    ex = _case()
    out = _wired(ex, interrupt_stale=False, sandbox=tmp_path)
    payload = ex.analyze(out)
    assert out.retrieve_result.interrupt_ids == []
    assert payload["session_count"] == 2
    assert payload["write_role_visits"] == 1
    assert payload["decision_exists"] is True
    assert payload["written"] == ["decision.txt"]
    text = (tmp_path / "decision.txt").read_text(encoding="utf-8")
    assert "Refunds are allowed" in text
    assert "2019" not in text
    assert payload["forwarded"] and "in force" in payload["forwarded"]
    assert out.write_result is not None
    assert out.write_tool.calls == [
        {"name": "write", "args": {"path": "decision.txt", "content": payload["forwarded"]}}
    ]


def test_two_sessions_two_tool_sets(tmp_path: Path):
    ex = _case()
    out = _wired(ex, interrupt_stale=False, sandbox=tmp_path)
    assert out.session_count == 2
    assert out.session_tools == ["retrieve", "write"]
    assert out.retrieve_tool is not out.write_tool
    assert all(c["name"] == "retrieve" for c in out.retrieve_tool.calls)
    assert all(c["name"] == "write" for c in out.write_tool.calls)
    assert "write" not in {c["name"] for c in out.retrieve_tool.calls}
    assert "retrieve" not in {c["name"] for c in out.write_tool.calls}


def test_case_is_two_session_roles_not_package_or_mesh(tmp_path: Path):
    pytest.importorskip("crewai")
    from crewai import Process

    text = (CASE / "graph.py").read_text(encoding="utf-8")
    public = (REPO / "interrupthink" / "__init__.py").read_text(encoding="utf-8")
    adr = (REPO / "plan" / "decisions" / "0008-multi-specialist-pipeline.md").read_text(
        encoding="utf-8"
    )
    assert "from interrupthink import" in text
    assert "LiveOpenAILlm" in text
    assert "run_session" in text
    assert "Process.sequential" in text
    assert "allow_delegation=False" in text
    assert "process=Process.hierarchical" not in text
    assert "kickoff(" not in text
    assert "execute_tools_when_ok=False" not in text
    assert "run_crewai_pipe" not in public
    assert "FixtureRetrieveTool" not in public
    assert "**proposed**" in adr
    assert "Status: **accepted**" not in adr
    ex = _case()
    out = _wired(ex, interrupt_stale=True, sandbox=tmp_path)
    assert out.crew.process == Process.sequential
    assert out.retrieve_agent.allow_delegation is False
    assert out.write_agent.allow_delegation is False


def test_example_calls_interruptible_not_the_case():
    example = (REPO / "examples" / "crewai_two_specialists.py").read_text(encoding="utf-8")
    assert "LiveOpenAILlm" in example
    assert "FakeLlm" not in example
    assert "run_session" in example
    assert "Process.sequential" in example
    assert "allow_delegation=False" in example
    assert "kickoff(" not in example
    assert "process=Process.hierarchical" not in example
    assert "importlib" not in example
    assert "spec_from_file_location" not in example
    assert "run_crewai_pipe" not in example
    assert "accepted" not in example.lower()
