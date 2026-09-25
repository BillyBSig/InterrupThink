"""Host gives the rest of the task to a new owner. The first specialist does not resume.

Scenario
    The supervisor may name ``editor`` or ``human``. The first specialist stops.
    ``editor`` starts from the kept steps, and a tool already written is not run
    again. ``human`` holds that same watermark. The monitor does not write the answer.

Expected
    Without a name, the first specialist finishes.
    With ``editor``, the editor finishes and the first model does not continue.
    With ``human``, no second specialist starts.

Usage (repo root; no API key)::

    pip install -e .
    python3 examples/dummy/supervisor_takeover.py
"""

from interrupthink import FakeLlm, ScriptedMonitor, run_session

HANDRAISE = """
tool_intent reversible: {"name":"write_note","args":{"text":"draft"}}
claim: the supervisor should take this
answer: I will finish it myself.
"""

LEFT_UNREAD = """
claim: I resume the same draft
answer: Still me.
"""

EDITOR = """
tool_intent reversible: {"name":"write_note","args":{"text":"draft"}}
claim: the note is now with the editor
answer: The editor holds the rest.
"""


def run_named_takeover(monitor: ScriptedMonitor):
    """Return the stopped result, the new owner result, and the first model."""
    original = FakeLlm([HANDRAISE, LEFT_UNREAD])
    first = run_session(llm=original, monitor=monitor)
    if first.takeover_to not in {"editor", "human"}:
        return first, None, original
    if first.takeover_to == "human":
        return first, None, original
    note = next(event.payload for event in first.events if event.type == "floor.takeover")
    editor = FakeLlm([EDITOR])
    editor.apply_resume(str(note["prefix"]))
    written = {str(call["name"]) for call in note["tool_calls"]}
    second = run_session(
        llm=editor,
        monitor=monitor,
        tool_policy=lambda name, args: name not in written,
    )
    return first, second, original


def main() -> None:
    editor_monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="the supervisor should take this",
        takeover_to="editor",
    )
    human_monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="the supervisor should take this",
        takeover_to="human",
    )
    editor_first, editor_second, _original = run_named_takeover(editor_monitor)
    human_first, human_second, _human_original = run_named_takeover(human_monitor)
    print(
        "editor",
        editor_first.takeover_to,
        None if editor_second is None else editor_second.committed_answer,
    )
    print("human", human_first.takeover_to, human_second)


if __name__ == "__main__":
    main()
