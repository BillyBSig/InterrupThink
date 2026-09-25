"""The host gives the named specialist enough to continue."""

import importlib.util
from pathlib import Path

from interrupthink import ScriptedMonitor

REPO = Path(__file__).resolve().parents[1]


def _example():
    path = REPO / "examples" / "dummy" / "supervisor_handoff.py"
    spec = importlib.util.spec_from_file_location("supervisor_handoff", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_unnamed_writer_receives_nothing():
    first, second, received = _example().run_named_handoff(ScriptedMonitor(trigger_kind=None))
    assert first.escalate_to == ""
    assert first.committed_answer == "I will finish the note myself."
    assert second is None
    assert received == ""


def test_named_writer_receives_task_prefix_and_written_tool():
    example = _example()
    monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="needs the writer",
        escalate_to="writer",
    )
    first, second, received = example.run_named_handoff(monitor)
    note = next(event.payload for event in first.events if event.type == "floor.escalate")
    assert received == example.writer_input(
        example.TASK,
        note,
        str(note["escalate_to"]),
        str(note["reason"]),
    )
    assert example.TASK in received
    assert "role: writer" in received
    assert note["reason"] == "named specialist"
    assert "reason: named specialist" in received
    assert "this needs the writer" in received
    assert "do not repeat: write_note" in received
    assert second is not None
    assert second.committed_answer == "Wrote the note."
    assert second.escalate_to == ""
    assert example.TASK in second.prefix
    assert "role: writer" in second.prefix
    assert "reason: named specialist" in second.prefix
    assert "this needs the writer" in second.prefix
    assert "do not repeat: write_note" in second.prefix
    assert "I will finish the note myself." not in second.prefix
    assert "the note is ready for the reader" not in second.prefix
    assert second.tool_calls == []
    assert any(event.type == "monitor.verdict" for event in second.events)
    denied = [row["name"] for row in second.log_records if row["event"] == "tool.policy.deny"]
    assert denied == ["write_note"]


def test_example_keeps_composition_on_the_host():
    text = (REPO / "examples" / "dummy" / "supervisor_handoff.py").read_text(encoding="utf-8")
    assert "def writer_input" in text
    assert "Write the public release note." in text
    assert "from src." not in text
    assert "transfer_to_" not in text
    assert "OPENAI" not in text
