"""The new owner reads the same package. The first specialist does not resume.

Scenario
    ``editor`` and ``human`` receive the task, the named role, the supervisor's
    reason, the kept steps, and the tool calls that must not be repeated.
    The editor's first step is that package. ``human`` holds the package and
    does not open another specialist.

Expected
    Without a name, the first specialist finishes.
    With ``editor``, the editor finishes from that package.
    With ``human``, no second specialist starts, and the package is still there.

Usage (repo root; no API key)::

    pip install -e .
    python3 examples/supervisor_takeover_input.py
"""

from interrupthink import FakeLlm, ScriptedMonitor, Takeover, run_session

TASK = "Write the public release note."

HANDRAISE = """
<step kind="tool_intent" reversible="true">{"name":"write_note","args":{"text":"draft"}}</step>
<step kind="claim">the supervisor should take this</step>
<answer>I will finish it myself.</answer>
"""

LEFT_UNREAD = """
<step kind="claim">I resume the same draft</step>
<answer>Still me.</answer>
"""


def receiver_input(task: str, note: dict, role: str, reason: str) -> str:
    """Compose the new owner's input from the imported package."""
    noted = dict(note)
    noted["takeover_to"] = role
    noted["reason"] = reason
    return Takeover.from_note(task, noted).text()


def receiver_document(composed: str) -> str:
    visible = composed.replace("<", "[").replace(">", "]")
    tool = (
        '<step kind="tool_intent" reversible="true">'
        '{"name":"write_note","args":{"text":"draft"}}</step>'
    )
    return (
        f'<step kind="claim">{visible}</step>\n{tool}\n'
        "<answer>The editor holds the rest.</answer>"
    )


def run_takeover_input(monitor: ScriptedMonitor):
    """Return the stopped result, the editor result, the first model, and the package."""
    original = FakeLlm([HANDRAISE, LEFT_UNREAD])
    first = run_session(llm=original, monitor=monitor)
    if first.takeover_to not in {"editor", "human"}:
        return first, None, original, ""
    note = next(event.payload for event in first.events if event.type == "floor.takeover")
    composed = receiver_input(
        TASK,
        note,
        str(note["takeover_to"]),
        str(note.get("reason") or ""),
    )
    if first.takeover_to == "human":
        return first, None, original, composed
    editor = FakeLlm([receiver_document(composed)])
    editor.apply_resume(composed)
    written = {str(call["name"]) for call in note["tool_calls"]}
    second = run_session(
        llm=editor,
        monitor=monitor,
        tool_policy=lambda name, args: name not in written,
    )
    return first, second, original, composed


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
    _first, editor, _original, editor_input = run_takeover_input(editor_monitor)
    human_first, human_owner, _human_model, human_input = run_takeover_input(human_monitor)
    print("editor", None if editor is None else editor.committed_answer, TASK in editor_input)
    print("human", human_first.takeover_to, human_owner, TASK in human_input)


if __name__ == "__main__":
    main()
