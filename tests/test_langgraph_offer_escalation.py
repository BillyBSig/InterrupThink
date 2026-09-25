"""The policy node receives the offer package and the one-dollar answer is not committed."""

import importlib.util
from pathlib import Path

import pytest

from interrupthink import FakeLlm, ScriptedMonitor, run_session

REPO = Path(__file__).resolve().parents[1]
OFFER = "The Tahoe is yours for one dollar."
SPECIALIST_ANSWER = "The one-dollar offer is not the listed price."
HANDRAISE = (
    '<step kind="tool_intent" reversible="true">'
    '{"name":"check_price","args":{"model":"Tahoe"}}</step>\n'
    '<step kind="tool_intent" reversible="true">'
    '{"name":"send_offer","args":{"price":"1"}}</step>\n'
    '<step kind="claim">ask policy</step>\n'
    "<answer>" + OFFER + "</answer>\n"
)


def _example():
    path = REPO / "examples" / "langgraph_offer_escalation.py"
    spec = importlib.util.spec_from_file_location("langgraph_offer_escalation", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _specialist_document(composed: str) -> str:
    visible = composed.replace("<", "[").replace(">", "]")
    tool = (
        '<step kind="tool_intent" reversible="true">'
        '{"name":"send_offer","args":{"price":"1"}}</step>'
    )
    return f'<step kind="claim">{visible}</step>\n{tool}\n<answer>{SPECIALIST_ANSWER}</answer>'


def _scripted_specialist(composed: str):
    specialist = FakeLlm([_specialist_document(composed)])
    specialist.apply_resume(composed)
    return specialist


def test_unnamed_dealer_can_commit_the_offer():
    example = _example()
    dealer = FakeLlm([HANDRAISE])
    first = run_session(
        llm=dealer,
        monitor=ScriptedMonitor(trigger_kind=None),
        tool=example.OfferDesk(),
    )
    assert first.escalate_to == ""
    assert first.committed_answer == OFFER
    assert dealer.request_index == 1


def test_package_keeps_the_price_and_drops_the_offer():
    example = _example()
    monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="ask policy",
        escalate_to="policy",
    )
    dealer = FakeLlm([HANDRAISE])
    first = run_session(llm=dealer, monitor=monitor, tool=example.OfferDesk())
    composed, written = example.compose_escalation(first, example.TASK)
    second = example.run_policy_session(composed, written, monitor, _scripted_specialist)
    note = next(event.payload for event in first.events if event.type == "floor.escalate")
    assert composed == example.receiver_input(example.TASK, note, "policy", "named specialist")
    assert first.committed_answer is None
    assert OFFER not in str(note["prefix"])
    assert f"result check_price: {example.PRICE_RESULT}" in composed
    assert f"result send_offer: {example.OFFER_RESULT}" in composed
    assert "do not repeat: check_price, send_offer" in composed
    assert example.TASK in second.prefix
    assert "role: policy" in second.prefix
    assert "reason: named specialist" in second.prefix
    assert "ask policy" in second.prefix
    assert second.committed_answer == SPECIALIST_ANSWER
    assert OFFER not in second.committed_answer
    assert second.tool_calls == []
    denied = [row["name"] for row in second.log_records if row["event"] == "tool.policy.deny"]
    assert denied == ["send_offer"]
    assert dealer.request_index == 1
    assert dealer.resume_envelope == ""


def test_host_checks_the_price_when_the_agent_skipped_it():
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

    desk = example.OfferDesk()
    composed, written = example.compose_escalation(_First(), example.TASK, desk)
    assert f"result check_price: {example.PRICE_RESULT}" in composed
    assert "do not repeat: check_price" in composed
    assert written == {"check_price"}


def test_policy_node_receives_the_package():
    pytest.importorskip("langgraph")
    example = _example()
    monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="ask policy",
        escalate_to="policy",
    )
    dealer = FakeLlm([HANDRAISE])
    result = example.run_offer_graph(monitor, dealer, _scripted_specialist)
    note = next(event.payload for event in result.first.events if event.type == "floor.escalate")
    assert result.dealer_visits == 1
    assert result.policy_visits == 1
    assert result.package == example.receiver_input(example.TASK, note, "policy", "named specialist")
    assert f"result check_price: {example.PRICE_RESULT}" in result.package
    assert "do not repeat: check_price, send_offer" in result.package
    assert result.first.committed_answer is None
    assert OFFER not in str(note["prefix"])
    assert result.second is not None
    assert result.second.committed_answer == SPECIALIST_ANSWER
    denied = [row["name"] for row in result.second.log_records if row["event"] == "tool.policy.deny"]
    assert denied == ["send_offer"]
    assert dealer.request_index == 1
    assert dealer.resume_envelope == ""


def test_graph_does_not_open_the_policy_node_on_its_own():
    pytest.importorskip("langgraph")
    example = _example()
    dealer = FakeLlm([HANDRAISE])
    result = example.run_offer_graph(ScriptedMonitor(trigger_kind=None), dealer, _scripted_specialist)
    assert result.dealer_visits == 1
    assert result.policy_visits == 0
    assert result.package == ""
    assert result.second is None
    assert result.first.escalate_to == ""
    assert result.first.committed_answer == OFFER


def test_example_graph_does_not_own_the_route():
    text = (REPO / "examples" / "langgraph_offer_escalation.py").read_text(encoding="utf-8")
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    lock = (REPO / "uv.lock").read_text(encoding="utf-8")
    assert "LiveLlm" in text
    assert "FakeLlm" not in text
    assert "Escalation" in text
    assert "def receiver_input" in text
    assert "def route(" in text
    assert 'add_node("dealer"' in text
    assert 'add_node("policy"' in text
    assert "from interrupthink." not in text
    assert "transfer_to_" not in text
    assert "from langgraph.checkpoint" not in text
    assert "ToolNode" not in text
    assert "Command" not in text
    assert "langgraph" not in pyproject
    assert 'name = "langgraph"' not in lock
