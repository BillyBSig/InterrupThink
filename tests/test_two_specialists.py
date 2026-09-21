"""Native host, two run_session, one supervisor. No LangGraph. No package retriever."""

import importlib.util
from pathlib import Path

from interrupthink import FakeLlm, ScriptedMonitor

REPO = Path(__file__).resolve().parents[1]


def _case():
    path = REPO / "cases" / "two-specialists" / "run.py"
    spec = importlib.util.spec_from_file_location("two_specialists_run", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


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
        forwarded = (ex.FIXTURES / "current.txt").read_text(encoding="utf-8")
        write_llm = FakeLlm([ex._write_xml(forwarded)])
    return ex.run_two_specialists(
        interrupt_stale=interrupt_stale,
        sandbox=sandbox,
        retrieve_llm=retrieve_llm,
        write_llm=write_llm,
        monitor=monitor,
    )


def test_stale_claim_does_not_write_decision(tmp_path: Path):
    ex = _case()
    out = _wired(ex, interrupt_stale=True, sandbox=tmp_path)
    payload = ex.analyze(out)
    assert payload["decision_exists"] is False
    assert payload["write_calls"] == []
    assert out.write_result is None
    assert payload["session_count"] == 1
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


def test_case_is_native_host_not_framework_or_package_retriever():
    text = (REPO / "cases" / "two-specialists" / "run.py").read_text(encoding="utf-8")
    public = (REPO / "interrupthink" / "__init__.py").read_text(encoding="utf-8")
    assert "from interrupthink import" in text
    assert "SandboxWriteTool" in text
    assert "run_session" in text
    assert "LiveOpenAILlm" in text
    assert "class FixtureRetrieveTool" in text
    assert "DummyTool()" not in text
    assert "import langgraph" not in text
    assert "from langgraph" not in text
    assert "import langchain" not in text
    assert "import git" not in text
    assert "import qdrant" not in text
    assert "from qdrant" not in text
    assert "FixtureRetrieveTool" not in public
    assert "class Retrieve" not in public
