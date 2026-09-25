"""Second specialist starts only when the supervisor names them."""

import importlib.util
from pathlib import Path

from interrupthink import FakeLlm, ScriptedMonitor, Verdict, run_session

REPO = Path(__file__).resolve().parents[1]

HANDRAISE = """
<step kind="claim">this needs the writer</step>
<answer>I will finish the note myself.</answer>
"""


def _example():
    path = REPO / "examples" / "dummy" / "supervisor_escalation.py"
    spec = importlib.util.spec_from_file_location("supervisor_escalation", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class _UnknownWithName:
    def __init__(self) -> None:
        self.held_tool_ids: list[str] = []
        self.checks = 0

    def verdict(self, unit) -> Verdict:
        self.checks += 1
        return Verdict(
            unit_id=unit.id,
            status="Unknown",
            reason="not enough evidence",
            escalate_to="writer",
        )

    def release_tool(self, unit_id: str) -> Verdict:
        return Verdict(unit_id=unit_id, status="Ok", reason="release")


def _escalate_note(result):
    notes = [event.payload for event in result.events if event.type == "floor.escalate"]
    assert len(notes) == 1
    return notes[0]


def _escalate_log(result):
    rows = [row for row in result.log_records if row["event"] == "floor.escalate"]
    assert len(rows) == 1
    return rows[0]


def test_unnamed_monitor_does_not_start_the_writer():
    monitor = ScriptedMonitor(trigger_kind=None)
    first, second = _example().run_named_escalation(monitor)
    assert first.escalate_to == ""
    assert first.committed_answer == "I will finish the note myself."
    assert second is None
    assert first.request_count == 1


def test_named_writer_is_checked_by_the_same_monitor():
    monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="needs the writer",
        escalate_to="writer",
    )
    first, second = _example().run_named_escalation(monitor)
    assert first.escalate_to == "writer"
    assert first.request_count == 1
    assert first.committed_answer is None
    assert "floor.resume" not in {row["event"] for row in first.log_records}
    note = _escalate_note(first)
    assert note["escalate_to"] == "writer"
    assert note["step_ids"]
    assert "needs the writer" in note["prefix"]
    logged = _escalate_log(first)
    assert logged["escalate_to"] == "writer"
    assert logged["step_ids"] == note["step_ids"]
    assert logged["prefix"]["redacted"] is True
    assert second is not None
    assert second.committed_answer == "Wrote the note."
    assert second.escalate_to == ""
    assert any(event.type == "monitor.verdict" for event in second.events)


def test_unknown_does_not_route_even_with_a_name():
    monitor = _UnknownWithName()
    result = run_session(llm=FakeLlm([HANDRAISE]), monitor=monitor)
    assert result.escalate_to == ""
    assert result.request_count == 1
    assert monitor.checks >= 1
    assert not any(event.type == "floor.escalate" for event in result.events)
    assert "floor.escalate" not in {row["event"] for row in result.log_records}


TOOL_THEN_HANDRAISE = """
<step kind="tool_intent" reversible="true">{"name":"write_note","args":{"text":"draft"}}</step>
<step kind="claim">this needs the writer</step>
"""


def test_handoff_note_lists_the_call_that_must_not_repeat():
    monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="needs the writer",
        escalate_to="writer",
    )
    result = run_session(llm=FakeLlm([TOOL_THEN_HANDRAISE]), monitor=monitor)
    note = _escalate_note(result)
    assert note["escalate_to"] == "writer"
    assert note["tool_calls"] == [{"name": "write_note", "args": {"text": "draft"}}]
    assert _escalate_log(result)["tool_calls"] == ["write_note"]


def test_example_does_not_let_the_specialist_call_its_peer():
    text = (REPO / "examples" / "dummy" / "supervisor_escalation.py").read_text(encoding="utf-8")
    assert "escalate_to=\"writer\"" in text
    assert "from interrupthink." not in text
    assert "transfer_to_" not in text
    assert "OPENAI" not in text
