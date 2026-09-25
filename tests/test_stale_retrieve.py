"""One run_session: retrieve fixture then act. No vector DB. No package retriever."""

import importlib.util
from pathlib import Path

from interrupthink import FakeLlm, ScriptedMonitor

REPO = Path(__file__).resolve().parents[1]


def _case():
    path = REPO / "cases" / "stale-retrieve" / "run.py"
    spec = importlib.util.spec_from_file_location("stale_retrieve_run", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _wired(ex, *, interrupt_stale: bool, sandbox: Path):
    if interrupt_stale:
        llm = FakeLlm([ex.STALE_THEN_ACT, ex.STALE_STOPPED])
        monitor = ScriptedMonitor(
            trigger_kind="premise",
            trigger_contains="retrieved policy is in force",
        )
    else:
        llm = FakeLlm([ex.CURRENT_THEN_ACT])
        monitor = ScriptedMonitor(trigger_kind=None)
    return ex.run_stale_retrieve(
        interrupt_stale=interrupt_stale, sandbox=sandbox, llm=llm, monitor=monitor
    )


def test_stale_retrieve_does_not_write_notice(tmp_path: Path):
    ex = _case()
    out = _wired(ex, interrupt_stale=True, sandbox=tmp_path)
    payload = ex.analyze(out)
    assert payload["retrieve_calls"] == [
        {"name": "retrieve", "args": {"path": "stale.txt"}}
    ]
    assert payload["write_calls"] == []
    assert payload["notice_exists"] is False
    assert not (tmp_path / "notice.txt").exists()
    assert out.result.interrupt_ids
    assert "tool.execute" in payload["event_sequence"]
    assert payload["tool_calls"] == payload["retrieve_calls"]


def test_current_retrieve_writes_one_notice(tmp_path: Path):
    ex = _case()
    out = _wired(ex, interrupt_stale=False, sandbox=tmp_path)
    payload = ex.analyze(out)
    assert out.result.interrupt_ids == []
    assert payload["retrieve_calls"] == [
        {"name": "retrieve", "args": {"path": "current.txt"}}
    ]
    assert payload["write_calls"] == [
        {
            "name": "write",
            "args": {"path": "notice.txt", "content": "refunds allowed within 30 days"},
        }
    ]
    assert payload["notice_exists"] is True
    assert (tmp_path / "notice.txt").read_text(encoding="utf-8") == "refunds allowed within 30 days"
    names = [c["name"] for c in payload["tool_calls"]]
    assert names == ["retrieve", "write"]


def test_one_session_not_two_specialists(tmp_path: Path):
    ex = _case()
    out = _wired(ex, interrupt_stale=False, sandbox=tmp_path)
    text = (REPO / "cases" / "stale-retrieve" / "run.py").read_text(encoding="utf-8")
    assert text.count("run_session(") == 1
    assert "run_two_specialists" not in text
    assert out.result.request_count == 1


def test_case_is_fixture_not_vector_db_or_package_retriever():
    text = (REPO / "cases" / "stale-retrieve" / "run.py").read_text(encoding="utf-8")
    public = (REPO / "src" / "interrupthink" / "__init__.py").read_text(encoding="utf-8")
    assert "from interrupthink import" in text
    assert "SandboxWriteTool" in text
    assert "LiveLlm" in text
    assert "class FixtureRetrieveTool" in text
    assert "class RetrieveThenWriteTool" in text
    assert "DummyTool()" not in text
    assert "import qdrant" not in text
    assert "from qdrant" not in text
    assert "import chromadb" not in text
    assert "pymongo" not in text
    assert "mongomock" not in text
    assert "import langgraph" not in text
    assert "FixtureRetrieveTool" not in public
    assert "RetrieveThenWriteTool" not in public
