"""Editor and human receive the same package. The first specialist does not resume."""

import importlib.util
from pathlib import Path

from interrupthink import ScriptedMonitor

REPO = Path(__file__).resolve().parents[1]


def _example():
    path = REPO / "examples" / "dummy" / "supervisor_takeover_input.py"
    spec = importlib.util.spec_from_file_location("supervisor_takeover_input", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _package(example, note):
    return example.receiver_input(
        example.TASK,
        note,
        str(note["takeover_to"]),
        str(note["reason"]),
    )


def test_unnamed_owner_receives_nothing():
    first, owner, original, received = _example().run_takeover_input(ScriptedMonitor(trigger_kind=None))
    assert first.takeover_to == ""
    assert first.committed_answer == "I will finish it myself."
    assert owner is None
    assert received == ""
    assert original.request_index == 1
    assert original.resume_envelope == ""


def test_editor_reads_the_package_and_the_first_specialist_stays_stopped():
    example = _example()
    monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="the supervisor should take this",
        takeover_to="editor",
    )
    first, owner, original, received = example.run_takeover_input(monitor)
    note = next(event.payload for event in first.events if event.type == "floor.takeover")
    assert note["reason"] == "named owner"
    assert received == _package(example, note)
    assert owner is not None
    assert example.TASK in owner.prefix
    assert "role: editor" in owner.prefix
    assert "reason: named owner" in owner.prefix
    assert "the supervisor should take this" in owner.prefix
    assert "do not repeat: write_note" in owner.prefix
    assert "I will finish it myself." not in owner.prefix
    assert owner.committed_answer == "The editor holds the rest."
    assert owner.takeover_to == ""
    assert owner.tool_calls == []
    denied = [row["name"] for row in owner.log_records if row["event"] == "tool.policy.deny"]
    assert denied == ["write_note"]
    assert original.request_index == 1
    assert original.resume_envelope == ""


def test_human_receives_the_same_package_without_another_specialist():
    example = _example()
    monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="the supervisor should take this",
        takeover_to="human",
    )
    first, owner, original, received = example.run_takeover_input(monitor)
    note = next(event.payload for event in first.events if event.type == "floor.takeover")
    assert owner is None
    assert received == _package(example, note)
    assert "role: human" in received
    assert "reason: named owner" in received
    assert example.TASK in received
    assert "the supervisor should take this" in received
    assert "do not repeat: write_note" in received
    assert original.request_index == 1
    assert original.resume_envelope == ""


def test_example_keeps_composition_on_the_host():
    text = (REPO / "examples" / "dummy" / "supervisor_takeover_input.py").read_text(encoding="utf-8")
    assert "def receiver_input" in text
    assert 'takeover_to="human"' in text
    assert "from src." not in text
    assert "transfer_to_" not in text
    assert "OPENAI" not in text
