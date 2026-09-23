"""A consult returns as a patch to the same specialist."""

import importlib.util
from pathlib import Path

from interrupthink import FakeLlm, ScriptedMonitor, Verdict, run_session

REPO = Path(__file__).resolve().parents[1]

HANDRAISE = """
<step kind="claim">ask the checker</step>
<answer>I will finish without a check.</answer>
"""


def _example():
    path = REPO / "examples" / "supervisor_consult.py"
    spec = importlib.util.spec_from_file_location("supervisor_consult", path)
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
            consult_to="checker",
        )

    def release_tool(self, unit_id: str) -> Verdict:
        return Verdict(unit_id=unit_id, status="Ok", reason="release")


class _ConsultThenUnknown:
    def __init__(self) -> None:
        self.held_tool_ids: list[str] = []
        self.checks = 0

    def verdict(self, unit) -> Verdict:
        self.checks += 1
        if self.checks == 1:
            return Verdict(
                unit_id=unit.id,
                status="Ok",
                reason="named consult",
                consult_to="checker",
            )
        return Verdict(unit_id=unit.id, status="Unknown", reason="not enough evidence")

    def release_tool(self, unit_id: str) -> Verdict:
        return Verdict(unit_id=unit_id, status="Ok", reason="release")


def test_unnamed_monitor_does_not_start_the_checker():
    first, consult, resumed = _example().run_named_consult(ScriptedMonitor(trigger_kind=None))
    assert first.consult_to == ""
    assert first.escalate_to == ""
    assert first.committed_answer == "I will finish without a check."
    assert consult is None
    assert resumed is None


def test_checked_consult_patches_the_same_specialist():
    monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="ask the checker",
        consult_to="checker",
    )
    first, consult, resumed = _example().run_named_consult(monitor)
    assert first.consult_to == "checker"
    assert first.escalate_to == ""
    assert "floor.resume" not in {row["event"] for row in first.log_records}
    assert "floor.escalate" not in {event.type for event in first.events}
    note = next(event.payload for event in first.events if event.type == "floor.consult")
    assert note["consult_to"] == "checker"
    assert consult is not None
    assert consult.committed_answer == "The checker confirms the draft."
    assert consult.escalate_to == ""
    assert any(event.type == "monitor.verdict" for event in consult.events)
    assert resumed is not None
    assert resumed.committed_answer == "Finished after the check."
    assert resumed.escalate_to == ""
    assert resumed.consult_to == ""
    assert resumed.tool_calls == []
    injected = [event.payload["patch"]["directive"] for event in resumed.events if event.type == "floor.inject"]
    assert injected == ["The checker confirms the draft."]
    denied = [row for row in resumed.log_records if row["event"] == "tool.policy.deny"]
    assert [row["name"] for row in denied] == ["lookup_note"]


def test_unknown_does_not_open_a_consult():
    result = run_session(llm=FakeLlm([HANDRAISE]), monitor=_UnknownWithName())
    assert result.consult_to == ""
    assert result.escalate_to == ""
    assert not any(event.type == "floor.consult" for event in result.events)


def test_unchecked_consult_does_not_resume_the_specialist():
    first, consult, resumed = _example().run_named_consult(_ConsultThenUnknown())
    assert first.consult_to == "checker"
    assert consult is not None
    assert consult.committed_answer is None
    assert resumed is None


def test_example_does_not_let_the_specialist_call_its_peer():
    text = (REPO / "examples" / "supervisor_consult.py").read_text(encoding="utf-8")
    assert "consult_to=\"checker\"" in text
    assert "from src." not in text
    assert "transfer_to_" not in text
    assert "OPENAI" not in text
