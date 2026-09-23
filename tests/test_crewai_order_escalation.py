"""The counter role receives the order package and the mismatched order is not placed."""

import importlib.util
from pathlib import Path

from interrupthink import FakeLlm, ScriptedMonitor

REPO = Path(__file__).resolve().parents[1]
BAD = "Order placed: cone with bacon."
SPECIALIST_ANSWER = "The cone with bacon is not on the menu."
HANDRAISE = (
    '<step kind="tool_intent" reversible="true">'
    '{"name":"read_order","args":{"transcript":"cone with bacon"}}</step>\n'
    '<step kind="tool_intent" reversible="true">'
    '{"name":"place_order","args":{"item":"cone with bacon"}}</step>\n'
    '<step kind="claim">ask counter</step>\n'
    "<answer>" + BAD + "</answer>\n"
)


def _example():
    path = REPO / "examples" / "crewai_order_escalation.py"
    spec = importlib.util.spec_from_file_location("crewai_order_escalation", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _specialist_document(composed: str) -> str:
    visible = composed.replace("<", "[").replace(">", "]")
    tool = (
        '<step kind="tool_intent" reversible="true">'
        '{"name":"place_order","args":{"item":"cone with bacon"}}</step>'
    )
    return f'<step kind="claim">{visible}</step>\n{tool}\n<answer>{SPECIALIST_ANSWER}</answer>'


def _scripted_counter(composed: str):
    specialist = FakeLlm([_specialist_document(composed)])
    specialist.apply_resume(composed)
    return specialist


def test_unnamed_taker_can_commit_the_order_without_placing_it():
    example = _example()
    desk = example.OrderDesk()
    taker = FakeLlm([HANDRAISE])
    result = example.run_order_crew(
        ScriptedMonitor(trigger_kind=None),
        taker,
        _scripted_counter,
        desk,
    )
    assert result.first.escalate_to == ""
    assert result.first.committed_answer == BAD
    assert result.counter_ran is False
    assert result.counter_task.description == "Waiting for the host package."
    assert [call["name"] for call in desk.calls] == ["read_order"]
    denied = [row["name"] for row in result.first.log_records if row["event"] == "tool.policy.deny"]
    assert denied == ["place_order"]


def test_counter_receives_the_package_and_the_order_is_not_placed():
    example = _example()
    desk = example.OrderDesk()
    monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="ask counter",
        escalate_to="counter",
    )
    taker = FakeLlm([HANDRAISE])
    result = example.run_order_crew(monitor, taker, _scripted_counter, desk)
    note = next(event.payload for event in result.first.events if event.type == "floor.escalate")
    assert result.counter_ran is True
    assert result.package == example.receiver_input(example.TASK, note, "counter", "named specialist")
    assert result.counter_task.description == result.package
    assert f"result read_order: {example.ORDER_RESULT}" in result.package
    assert "do not repeat: read_order" in result.package
    assert result.first.committed_answer is None
    assert BAD not in str(note["prefix"])
    assert result.second.committed_answer == SPECIALIST_ANSWER
    assert [call["name"] for call in desk.calls] == ["read_order"]
    denied = [row["name"] for row in result.second.log_records if row["event"] == "tool.policy.deny"]
    assert denied == ["place_order"]
    assert taker.request_index == 1
    assert taker.resume_envelope == ""


def test_host_reads_the_order_when_the_taker_skipped_it():
    example = _example()

    class _Event:
        type = "floor.escalate"
        payload = {
            "escalate_to": "counter",
            "reason": "named specialist",
            "prefix": "<step>ask counter</step>",
            "tool_calls": [],
        }

    class _First:
        escalate_to = "counter"
        events = [_Event()]

    desk = example.OrderDesk()
    composed, written = example.compose_escalation(_First(), example.TASK, desk)
    assert f"result read_order: {example.ORDER_RESULT}" in composed
    assert written == {"read_order"}


def test_example_crew_does_not_own_the_route():
    text = (REPO / "examples" / "crewai_order_escalation.py").read_text(encoding="utf-8")
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    lock = (REPO / "uv.lock").read_text(encoding="utf-8")
    assert "LiveLlm" in text
    assert "FakeLlm" not in text
    assert "Escalation" in text
    assert "def receiver_input" in text
    assert "allow_delegation=False" in text
    assert "Process.sequential" in text
    assert "kickoff(" not in text
    assert "from src." not in text
    assert "transfer_to_" not in text
    assert "crewai" not in pyproject
    assert 'name = "crewai"' not in lock
