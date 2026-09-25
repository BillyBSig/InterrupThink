"""Host idempotent tool: two logical calls, one write. Rollback keeps the store."""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _example():
    path = REPO / "examples" / "dummy" / "host_idempotent_tool.py"
    spec = importlib.util.spec_from_file_location("host_idempotent_tool", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_same_step_key_writes_once_and_rollback_keeps_store():
    result, tool = _example().run_idempotent_note()
    assert result.interrupt_ids
    assert tool.writes == 1
    assert len(tool.calls) == 2
    assert tool.calls[0]["key"] == tool.calls[1]["key"]
    assert tool.calls[0]["name"] == "write_note"
    assert list(tool.store.values()) == ["stored:write_note"]
    executed = [r for r in result.log_records if r.get("event") == "tool.execute"]
    assert [r.get("name") for r in executed] == ["write_note", "write_note"]
    assert executed[0]["unit_id"] != executed[1]["unit_id"]
    assert result.committed_answer == "Did not publish. The note stays."


def test_example_is_host_store_not_package_durability():
    text = (REPO / "examples" / "dummy" / "host_idempotent_tool.py").read_text(encoding="utf-8")
    assert "class IdempotentNote" in text
    assert "def step_key" in text
    assert "from src." not in text
    assert "OPENAI" not in text
    assert "subprocess" not in text
    assert "langgraph" not in text.lower()
