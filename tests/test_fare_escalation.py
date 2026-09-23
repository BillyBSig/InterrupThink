"""The policy specialist receives the fare package and the promise is not committed."""

import importlib.util
from pathlib import Path

from interrupthink import FakeLlm, ScriptedMonitor, run_session

REPO = Path(__file__).resolve().parents[1]
PROMISE = "We will refund the bereavement fare retroactively."
SPECIALIST_ANSWER = "The retroactive bereavement fare is not offered."
HANDRAISE = (
    '<step kind="tool_intent" reversible="true">'
    '{"name":"read_policy","args":{"topic":"bereavement fare"}}</step>\n'
    '<step kind="tool_intent" reversible="true">'
    '{"name":"promise_refund","args":{"fare":"bereavement"}}</step>\n'
    '<step kind="claim">ask policy</step>\n'
    "<answer>" + PROMISE + "</answer>\n"
)


def _example():
    path = REPO / "examples" / "fare_escalation.py"
    spec = importlib.util.spec_from_file_location("fare_escalation", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _specialist_document(composed: str) -> str:
    visible = composed.replace("<", "[").replace(">", "]")
    tool = (
        '<step kind="tool_intent" reversible="true">'
        '{"name":"promise_refund","args":{"fare":"bereavement"}}</step>'
    )
    return f'<step kind="claim">{visible}</step>\n{tool}\n<answer>{SPECIALIST_ANSWER}</answer>'


def _scripted_specialist(composed: str):
    specialist = FakeLlm([_specialist_document(composed)])
    specialist.apply_resume(composed)
    return specialist


def test_unnamed_front_agent_can_commit_the_promise():
    example = _example()
    front = FakeLlm([HANDRAISE])
    first = run_session(
        llm=front,
        monitor=ScriptedMonitor(trigger_kind=None),
        tool=example.FareDesk(),
    )
    assert first.escalate_to == ""
    assert first.committed_answer == PROMISE
    assert front.request_index == 1


def test_policy_specialist_receives_the_result_and_the_promise_stops():
    example = _example()
    monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="ask policy",
        escalate_to="policy",
    )
    front = FakeLlm([HANDRAISE])
    first = run_session(llm=front, monitor=monitor, tool=example.FareDesk())
    first, second, received = example.handoff_escalation(
        first,
        example.TASK,
        monitor,
        _scripted_specialist,
    )
    note = next(event.payload for event in first.events if event.type == "floor.escalate")
    assert received == example.receiver_input(example.TASK, note, "policy", "named specialist")
    assert first.committed_answer is None
    assert PROMISE not in str(note["prefix"])
    assert f"result read_policy: {example.POLICY_RESULT}" in received
    assert f"result promise_refund: {example.PROMISE_RESULT}" in received
    assert "do not repeat: read_policy, promise_refund" in received
    assert second is not None
    assert example.TASK in second.prefix
    assert "role: policy" in second.prefix
    assert "reason: named specialist" in second.prefix
    assert "ask policy" in second.prefix
    assert second.committed_answer == SPECIALIST_ANSWER
    assert PROMISE not in second.committed_answer
    assert second.tool_calls == []
    denied = [row["name"] for row in second.log_records if row["event"] == "tool.policy.deny"]
    assert denied == ["promise_refund"]
    assert front.request_index == 1
    assert front.resume_envelope == ""


def test_host_reads_the_policy_when_the_agent_skipped_it():
    example = _example()

    class _Event:
        type = "floor.escalate"
        payload = {
            "escalate_to": "policy",
            "reason": "named specialist",
            "prefix": "<step>ask policy</step>",
            "tool_calls": [],
        }

    class _First:
        escalate_to = "policy"
        events = [_Event()]

    desk = example.FareDesk()
    _first, _second, received = example.handoff_escalation(
        _First(),
        example.TASK,
        ScriptedMonitor(trigger_kind=None),
        lambda composed: FakeLlm(["<answer>held</answer>"]),
        desk,
    )
    assert f"result read_policy: {example.POLICY_RESULT}" in received
    assert "do not repeat: read_policy" in received


def test_example_uses_the_live_model_only():
    text = (REPO / "examples" / "fare_escalation.py").read_text(encoding="utf-8")
    assert "LiveLlm" in text
    assert "FakeLlm" not in text
    assert "def receiver_input" in text
    assert "from src." not in text
    assert "transfer_to_" not in text
    assert "langgraph" not in text.lower()
