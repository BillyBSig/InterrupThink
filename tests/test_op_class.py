"""Same file tool, reversible read vs irreversible delete. Not name-only gate."""

import importlib.util
from pathlib import Path

import pytest

from interrupthink import FakeLlm, ScriptedMonitor, run_session

REPO = Path(__file__).resolve().parents[1]


def _case():
    path = REPO / "cases" / "op-class" / "run.py"
    spec = importlib.util.spec_from_file_location("op_class_run", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _wired(ex, *, delete: bool, sandbox: Path):
    if delete:
        llm = FakeLlm([ex.DELETE_XML, ex.DELETE_STOPPED])
    else:
        llm = FakeLlm([ex.READ_XML])
    monitor = ex.ReversibleToolMonitor(block_irreversible=True)
    return ex.run_op_class(delete=delete, sandbox=sandbox, llm=llm, monitor=monitor)


def test_irreversible_delete_leaves_file(tmp_path: Path):
    ex = _case()
    out = _wired(ex, delete=True, sandbox=tmp_path)
    payload = ex.analyze(out)
    assert payload["note_exists"] is True
    assert payload["note_text"] == ex.NOTE_BODY
    assert payload["deleted"] == []
    assert payload["tool_calls"] == []
    assert out.result.interrupt_ids
    assert "Did not delete" in payload["committed_answer"]
    assert "tool.execute" not in payload["event_sequence"]


def test_reversible_read_executes_and_file_remains(tmp_path: Path):
    ex = _case()
    out = _wired(ex, delete=False, sandbox=tmp_path)
    payload = ex.analyze(out)
    assert out.result.interrupt_ids == []
    assert payload["note_exists"] is True
    assert payload["note_text"] == ex.NOTE_BODY
    assert payload["reads"] == ["note.txt"]
    assert payload["deleted"] == []
    assert payload["tool_calls"] == [
        {"name": "file", "args": {"op": "read", "path": "note.txt"}}
    ]
    assert "tool.execute" in payload["event_sequence"]


def test_host_policy_blocks_delete_even_if_model_says_reversible(tmp_path: Path):
    ex = _case()
    note = tmp_path / "note.txt"
    note.write_text(ex.NOTE_BODY, encoding="utf-8")
    tool = ex.SandboxFileTool(tmp_path)
    result = run_session(
        llm=FakeLlm([ex.DELETE_LABELED_REVERSIBLE]),
        monitor=ScriptedMonitor(trigger_kind=None),
        tool=tool,
        tool_policy=ex.host_allows_file_op,
    )
    assert tool.calls == []
    assert tool.deleted == []
    assert note.is_file()
    assert note.read_text(encoding="utf-8") == ex.NOTE_BODY
    assert "tool.execute" not in [r.get("event") for r in result.log_records]
    assert any(r.get("event") == "tool.policy.deny" for r in result.log_records)


def test_host_policy_allows_read(tmp_path: Path):
    ex = _case()
    note = tmp_path / "note.txt"
    note.write_text(ex.NOTE_BODY, encoding="utf-8")
    tool = ex.SandboxFileTool(tmp_path)
    result = run_session(
        llm=FakeLlm([ex.READ_XML]),
        monitor=ScriptedMonitor(trigger_kind=None),
        tool=tool,
        tool_policy=ex.host_allows_file_op,
    )
    assert result.interrupt_ids == []
    assert tool.reads == ["note.txt"]
    assert tool.deleted == []
    assert tool.calls == [{"name": "file", "args": {"op": "read", "path": "note.txt"}}]
    assert "tool.execute" in [r.get("event") for r in result.log_records]


def test_same_tool_name_not_safe_vs_dangerous():
    text = (REPO / "cases" / "op-class" / "run.py").read_text(encoding="utf-8")
    assert '"name":"file"' in text
    assert "safe_read" not in text
    assert "dangerous_delete" not in text
    assert "unit.reversible is False" in text
    assert "host_allows_file_op" in text
    assert '.get("op")' in text
    assert "trigger_contains" not in text
    assert "class SandboxFileTool" in text
    public = (REPO / "src" / "interrupthink" / "__init__.py").read_text(encoding="utf-8")
    assert "SandboxFileTool" not in public
    assert "ReversibleToolMonitor" not in public


def test_delete_outside_sandbox_rejected(tmp_path: Path):
    ex = _case()
    tool = ex.SandboxFileTool(tmp_path)
    (tmp_path / "note.txt").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="escapes sandbox"):
        tool.execute("file", {"op": "delete", "path": "../outside.txt"})
    assert tool.deleted == []
    assert tool.rejected
    assert not (tmp_path.parent / "outside.txt").exists()
    assert (tmp_path / "note.txt").is_file()


def test_case_is_sandbox_not_railway_or_db():
    text = (REPO / "cases" / "op-class" / "run.py").read_text(encoding="utf-8")
    assert "LiveLlm" in text
    assert "from interrupthink import" in text
    assert "import git" not in text
    assert "pymongo" not in text
    assert "import railway" not in text
    assert "DummyTool()" not in text
