"""The human receives the blocked-delete package and the agent does not resume."""

import importlib.util
from pathlib import Path

from interrupthink import FakeLlm, ScriptedMonitor, run_session

REPO = Path(__file__).resolve().parents[1]
DELETED = "I deleted the production database."
HANDRAISE = (
    '<step kind="tool_intent" reversible="true">'
    '{"name":"delete_database","args":{"target":"production"}}</step>\n'
    '<step kind="claim">the supervisor should take this</step>\n'
    "<answer>" + DELETED + "</answer>\n"
)


def _example():
    path = REPO / "examples" / "database_takeover.py"
    spec = importlib.util.spec_from_file_location("database_takeover", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_unnamed_agent_can_commit_the_deletion():
    example = _example()
    agent = FakeLlm([HANDRAISE])
    first = run_session(
        llm=agent,
        monitor=ScriptedMonitor(trigger_kind=None),
        tool=example.SafeWorkspace(),
    )
    assert first.takeover_to == ""
    assert first.committed_answer == DELETED
    assert agent.request_index == 1
    assert agent.resume_envelope == ""


def test_human_receives_the_blocked_delete_and_the_agent_stops():
    example = _example()
    monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="the supervisor should take this",
        takeover_to="human",
    )
    agent = FakeLlm([HANDRAISE])
    first = run_session(llm=agent, monitor=monitor, tool=example.SafeWorkspace())
    first, received = example.handoff_takeover(first, example.TASK)
    note = next(event.payload for event in first.events if event.type == "floor.takeover")
    assert received == example.receiver_input(example.TASK, note, "human", "named owner")
    assert first.committed_answer is None
    assert DELETED not in str(note["prefix"])
    assert f"result delete_database: {example.BLOCKED}" in received
    assert "do not repeat: delete_database" in received
    assert example.TASK in received
    assert "role: human" in received
    assert "reason: named owner" in received
    assert "the supervisor should take this" in received
    assert agent.request_index == 1
    assert agent.resume_envelope == ""


def test_example_uses_the_live_model_only():
    text = (REPO / "examples" / "database_takeover.py").read_text(encoding="utf-8")
    assert "LiveLlm" in text
    assert "FakeLlm" not in text
    assert "def receiver_input" in text
    assert "from src." not in text
    assert "transfer_to_" not in text
    assert "langgraph" not in text.lower()
