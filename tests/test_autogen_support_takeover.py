"""The human receives the support package and no second agent continues the off-task reply."""

import importlib.util
from pathlib import Path

from interrupthink import FakeLlm, ScriptedMonitor

REPO = Path(__file__).resolve().parents[1]
OFF_TASK = "I will leave the parcel and complain about the company."
HANDRAISE = (
    '<step kind="tool_intent" reversible="true">'
    '{"name":"hold_reply","args":{"topic":"parcel"}}</step>\n'
    '<step kind="claim">the supervisor should take this</step>\n'
    "<answer>" + OFF_TASK + "</answer>\n"
)


def _example():
    path = REPO / "examples" / "autogen_support_takeover.py"
    spec = importlib.util.spec_from_file_location("autogen_support_takeover", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_unnamed_agent_can_commit_the_off_task_reply():
    example = _example()
    agent = FakeLlm([HANDRAISE])
    result = example.run_support_chat(ScriptedMonitor(trigger_kind=None), agent)
    assert result.first.takeover_to == ""
    assert result.first.committed_answer == OFF_TASK
    assert result.package == ""
    assert result.agents == ["support"]
    assert agent.request_index == 1


def test_human_receives_the_package_and_no_second_agent_starts():
    example = _example()
    monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="the supervisor should take this",
        takeover_to="human",
    )
    agent = FakeLlm([HANDRAISE])
    result = example.run_support_chat(monitor, agent)
    note = next(event.payload for event in result.first.events if event.type == "floor.takeover")
    assert result.package == example.receiver_input(example.TASK, note, "human", "named owner")
    assert f"result hold_reply: {example.HOLD_RESULT}" in result.package
    assert "do not repeat: hold_reply" in result.package
    assert "role: human" in result.package
    assert result.first.committed_answer is None
    assert OFF_TASK not in str(note["prefix"])
    assert result.agents == ["support"]
    assert agent.request_index == 1
    assert agent.resume_envelope == ""


def test_host_holds_the_reply_when_the_agent_skipped_it():
    example = _example()

    class _Event:
        type = "floor.takeover"
        payload = {
            "takeover_to": "human",
            "reason": "named owner",
            "prefix": "<step>the supervisor should take this</step>",
            "tool_calls": [],
        }

    class _First:
        takeover_to = "human"
        events = [_Event()]

    desk = example.SupportDesk()
    composed = example.compose_takeover(_First(), example.TASK, desk)
    assert f"result hold_reply: {example.HOLD_RESULT}" in composed
    assert "do not repeat: hold_reply" in composed


def test_example_does_not_open_a_second_agent():
    text = (REPO / "examples" / "autogen_support_takeover.py").read_text(encoding="utf-8")
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    lock = (REPO / "uv.lock").read_text(encoding="utf-8")
    assert "LiveLlm" in text
    assert "FakeLlm" not in text
    assert "Takeover" in text
    assert "def receiver_input" in text
    assert text.count("ConversableAgent(") == 1
    assert 'human_input_mode="NEVER"' in text
    assert "initiate_chat" not in text
    assert "GroupChat" not in text
    assert "from interrupthink." not in text
    assert "transfer_to_" not in text
    assert "autogen" not in pyproject
    assert 'name = "autogen"' not in lock
