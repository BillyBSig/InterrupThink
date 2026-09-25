"""After takeover the first specialist does not resume."""

import importlib.util
from pathlib import Path

from interrupthink import FakeLlm, ScriptedMonitor, Verdict, run_session

REPO = Path(__file__).resolve().parents[1]

HANDRAISE = """
<step kind="tool_intent" reversible="true">{"name":"write_note","args":{"text":"draft"}}</step>
<step kind="claim">the supervisor should take this</step>
<answer>I will finish it myself.</answer>
"""


def _example():
    path = REPO / "examples" / "dummy" / "supervisor_takeover.py"
    spec = importlib.util.spec_from_file_location("supervisor_takeover", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class _UnknownWithName:
    def __init__(self) -> None:
        self.held_tool_ids: list[str] = []

    def verdict(self, unit) -> Verdict:
        return Verdict(
            unit_id=unit.id,
            status="Unknown",
            reason="not enough evidence",
            takeover_to="editor",
        )

    def release_tool(self, unit_id: str) -> Verdict:
        return Verdict(unit_id=unit_id, status="Ok", reason="release")


def test_unnamed_monitor_lets_the_first_specialist_finish():
    monitor = ScriptedMonitor(trigger_kind=None)
    first, owner, original = _example().run_named_takeover(monitor)
    assert first.takeover_to == ""
    assert first.escalate_to == ""
    assert first.consult_to == ""
    assert first.committed_answer == "I will finish it myself."
    assert owner is None
    assert original.request_index == 1
    assert original.resume_envelope == ""


def test_editor_starts_from_the_watermark_without_a_repeat_write():
    monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="the supervisor should take this",
        takeover_to="editor",
    )
    first, owner, original = _example().run_named_takeover(monitor)
    assert first.takeover_to == "editor"
    assert first.committed_answer is None
    assert first.escalate_to == ""
    assert first.consult_to == ""
    assert "floor.resume" not in {row["event"] for row in first.log_records}
    assert original.request_index == 1
    assert original.resume_envelope == ""
    note = next(event.payload for event in first.events if event.type == "floor.takeover")
    assert note["takeover_to"] == "editor"
    assert "the supervisor should take this" in note["prefix"]
    assert note["tool_calls"] == [{"name": "write_note", "args": {"text": "draft"}}]
    assert owner is not None
    assert owner.committed_answer == "The editor holds the rest."
    assert owner.takeover_to == ""
    assert owner.tool_calls == []
    assert any(event.type == "monitor.verdict" for event in owner.events)
    denied = [row["name"] for row in owner.log_records if row["event"] == "tool.policy.deny"]
    assert denied == ["write_note"]


def test_human_owner_does_not_start_another_specialist():
    monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="the supervisor should take this",
        takeover_to="human",
    )
    first, owner, original = _example().run_named_takeover(monitor)
    assert first.takeover_to == "human"
    assert first.committed_answer is None
    assert owner is None
    assert original.request_index == 1
    assert original.resume_envelope == ""
    note = next(event.payload for event in first.events if event.type == "floor.takeover")
    assert "the supervisor should take this" in note["prefix"]


def test_unknown_does_not_take_over():
    result = run_session(llm=FakeLlm([HANDRAISE]), monitor=_UnknownWithName())
    assert result.takeover_to == ""
    assert result.committed_answer is None
    assert not any(event.type == "floor.takeover" for event in result.events)


def test_example_does_not_let_the_monitor_write_the_answer():
    text = (REPO / "examples" / "dummy" / "supervisor_takeover.py").read_text(encoding="utf-8")
    assert 'takeover_to="editor"' in text
    assert 'takeover_to="human"' in text
    assert 'apply_resume(str(note["prefix"]))' in text
    assert "from src." not in text
    assert "transfer_to_" not in text
    assert "OPENAI" not in text
