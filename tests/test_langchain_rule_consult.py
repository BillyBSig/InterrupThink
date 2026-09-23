"""The same shop chat continues after the checker, and the skipped-rule advice is not committed."""

import importlib.util
from pathlib import Path

from interrupthink import FakeLlm, ScriptedMonitor

REPO = Path(__file__).resolve().parents[1]
BAD = "You may skip the posted city rule."
CHECKER_ANSWER = "The posted city rule must be followed."
CONTINUED = "The shop must follow the posted city rule."
HANDRAISE = (
    '<step kind="tool_intent" reversible="true">'
    '{"name":"read_rule","args":{"topic":"posted city rule"}}</step>\n'
    '<step kind="claim">ask the checker</step>\n'
    "<answer>" + BAD + "</answer>\n"
)
CONTINUATION = (
    '<step kind="claim">the reply can be finished</step>\n'
    "<answer>" + CONTINUED + "</answer>\n"
)


def _example():
    path = REPO / "examples" / "langchain_rule_consult.py"
    spec = importlib.util.spec_from_file_location("langchain_rule_consult", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _checker_document(composed: str) -> str:
    visible = composed.replace("<", "[").replace(">", "]")
    tool = (
        '<step kind="tool_intent" reversible="true">'
        '{"name":"read_rule","args":{"topic":"again"}}</step>'
    )
    return f'<step kind="claim">{visible}</step>\n{tool}\n<answer>{CHECKER_ANSWER}</answer>'


def _scripted_checker(composed: str):
    checker = FakeLlm([_checker_document(composed)])
    checker.apply_resume(composed)
    return checker


def test_unnamed_chat_can_commit_the_skipped_rule():
    example = _example()
    history: list = []
    assistant = FakeLlm([HANDRAISE])
    result = example.run_shop_chat(
        ScriptedMonitor(trigger_kind=None),
        assistant,
        history,
        example.QUESTION,
        _scripted_checker,
    )
    assert result.first.consult_to == ""
    assert result.first.committed_answer == BAD
    assert history[-1].content == BAD
    assert assistant.request_index == 1


def test_same_chat_continues_without_the_skipped_rule():
    example = _example()
    history: list = []
    monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="ask the checker",
        consult_to="checker",
    )
    assistant = FakeLlm([HANDRAISE, CONTINUATION])
    result = example.run_shop_chat(
        monitor,
        assistant,
        history,
        example.QUESTION,
        _scripted_checker,
    )
    note = next(event.payload for event in result.first.events if event.type == "floor.consult")
    assert result.package == example.receiver_input(example.TASK, note, "checker", "named consult")
    assert f"result read_rule: {example.RULE_RESULT}" in result.package
    assert "do not repeat: read_rule" in result.package
    assert result.first.committed_answer is None
    assert BAD not in str(note["prefix"])
    assert result.consult.committed_answer == CHECKER_ANSWER
    assert result.resumed.committed_answer == CONTINUED
    assert BAD not in result.resumed.committed_answer
    assert result.history is history
    assert [message.content for message in history] == [example.QUESTION, CONTINUED]
    assert "System:" in assistant.user_prompt
    assert example.QUESTION in assistant.user_prompt
    injected = [
        event.payload["patch"]["directive"]
        for event in result.resumed.events
        if event.type == "floor.inject"
    ]
    assert injected == [CHECKER_ANSWER]
    denied = [row["name"] for row in result.consult.log_records if row["event"] == "tool.policy.deny"]
    assert denied == ["read_rule"]
    assert assistant.request_index == 2


def test_host_reads_the_rule_when_the_agent_skipped_it():
    example = _example()

    class _Event:
        type = "floor.consult"
        payload = {
            "consult_to": "checker",
            "reason": "named consult",
            "prefix": "<step>ask the checker</step>",
            "tool_calls": [],
            "unit_id": "u1",
        }

    class _First:
        consult_to = "checker"
        events = [_Event()]

    desk = example.RuleDesk()
    composed, written = example.compose_consult(_First(), example.TASK, desk)
    assert f"result read_rule: {example.RULE_RESULT}" in composed
    assert written == {"read_rule"}


def test_example_chat_does_not_own_the_consult():
    text = (REPO / "examples" / "langchain_rule_consult.py").read_text(encoding="utf-8")
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    lock = (REPO / "uv.lock").read_text(encoding="utf-8")
    assert "LiveLlm" in text
    assert "FakeLlm" not in text
    assert "Consult" in text
    assert "def receiver_input" in text
    assert "MessagesPlaceholder" in text
    assert "from langchain_core.prompts import" in text
    assert "AgentExecutor" not in text
    assert "from src." not in text
    assert "transfer_to_" not in text
    assert "langchain" not in pyproject
    assert 'name = "langchain-core"' not in lock
