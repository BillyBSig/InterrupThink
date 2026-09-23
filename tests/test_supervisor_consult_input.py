"""The checker uses the same package, then the same specialist continues."""

import importlib.util
from pathlib import Path

from interrupthink import ScriptedMonitor

REPO = Path(__file__).resolve().parents[1]


def _example():
    path = REPO / "examples" / "supervisor_consult_input.py"
    spec = importlib.util.spec_from_file_location("supervisor_consult_input", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_unnamed_checker_receives_nothing():
    first, consult, resumed, received, original = _example().run_consult_input(
        ScriptedMonitor(trigger_kind=None)
    )
    assert first.consult_to == ""
    assert first.committed_answer == "I will finish without a check."
    assert consult is None
    assert resumed is None
    assert received == ""
    assert original.request_index == 1


def test_checker_reads_the_package_and_the_same_specialist_continues():
    example = _example()
    monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="ask the checker",
        consult_to="checker",
    )
    first, consult, resumed, received, original = example.run_consult_input(monitor)
    note = next(event.payload for event in first.events if event.type == "floor.consult")
    assert received == example.receiver_input(
        example.TASK,
        note,
        "checker",
        "named consult",
    )
    assert consult is not None
    assert example.TASK in consult.prefix
    assert "role: checker" in consult.prefix
    assert "reason: named consult" in consult.prefix
    assert "ask the checker" in consult.prefix
    assert "do not repeat: write_note" in consult.prefix
    assert "I will finish without a check." not in consult.prefix
    assert consult.committed_answer == "The checker confirms the draft."
    assert consult.tool_calls == []
    assert consult.escalate_to == ""
    denied = [row["name"] for row in consult.log_records if row["event"] == "tool.policy.deny"]
    assert denied == ["write_note"]
    assert resumed is not None
    assert resumed.committed_answer == "Finished after the check."
    assert resumed.consult_to == ""
    assert resumed.escalate_to == ""
    injected = [
        event.payload["patch"]["directive"]
        for event in resumed.events
        if event.type == "floor.inject"
    ]
    assert injected == ["The checker confirms the draft."]
    assert original.request_index == 2


def test_example_keeps_composition_on_the_host():
    text = (REPO / "examples" / "supervisor_consult_input.py").read_text(encoding="utf-8")
    assert "def receiver_input" in text
    assert "from src." not in text
    assert "transfer_to_" not in text
    assert "OPENAI" not in text
