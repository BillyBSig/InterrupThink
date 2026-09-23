"""The checker reads the same package, then the result returns to the same specialist.

Scenario
    The host gives the checker the task, the role ``checker``, the supervisor's
    reason, the kept steps, and the tool calls that must not be repeated.
    The checker's first step is that package. The checked answer comes back
    as a patch. The original specialist continues.

Expected
    Without a name, the checker receives nothing.
    With ``checker``, the original specialist finishes after the patch.

Usage (repo root; no API key)::

    pip install -e .
    python3 examples/supervisor_consult_input.py
"""

from interrupthink import Consult, FakeLlm, Patch, ScriptedMonitor, run_session

TASK = "Write the public release note."

HANDRAISE = """
<step kind="tool_intent" reversible="true">{"name":"write_note","args":{"text":"draft"}}</step>
<step kind="claim">ask the checker</step>
<answer>I will finish without a check.</answer>
"""

CONTINUATION = """
<step kind="tool_intent" reversible="true">{"name":"write_note","args":{"text":"draft"}}</step>
<step kind="claim">the note can be finished</step>
<answer>Finished after the check.</answer>
"""


def receiver_input(task: str, note: dict, role: str, reason: str) -> str:
    """Compose the checker's input from the imported package."""
    noted = dict(note)
    noted["consult_to"] = role
    noted["reason"] = reason
    return Consult.from_note(task, noted).text()


def receiver_document(composed: str, answer: str) -> str:
    visible = composed.replace("<", "[").replace(">", "]")
    tool = (
        '<step kind="tool_intent" reversible="true">'
        '{"name":"write_note","args":{"text":"draft"}}</step>'
    )
    return f'<step kind="claim">{visible}</step>\n{tool}\n<answer>{answer}</answer>'


def run_consult_input(monitor: ScriptedMonitor):
    """Return the opening, the checker, the resumed specialist, the input, and the model."""
    original = FakeLlm([HANDRAISE, CONTINUATION])
    first = run_session(llm=original, monitor=monitor)
    if first.consult_to != "checker":
        return first, None, None, "", original
    note = next(event.payload for event in first.events if event.type == "floor.consult")
    composed = receiver_input(TASK, note, str(note["consult_to"]), str(note.get("reason") or ""))
    checker = FakeLlm([receiver_document(composed, "The checker confirms the draft.")])
    checker.apply_resume(composed)
    written = {str(call["name"]) for call in note["tool_calls"]}
    consult = run_session(
        llm=checker,
        monitor=monitor,
        tool_policy=lambda name, args: name not in written,
    )
    if consult.committed_answer is None:
        return first, consult, None, composed, original
    patch = Patch(
        from_agent="A",
        target_unit_id=str(note["unit_id"]),
        rollback_to=None,
        diagnosis="consult",
        missing=consult.committed_answer,
        directive=consult.committed_answer,
    )
    resumed = run_session(
        llm=original,
        monitor=monitor,
        resume_patch=patch,
        tool_policy=lambda name, args: name not in written,
    )
    return first, consult, resumed, composed, original


def main() -> None:
    named = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="ask the checker",
        consult_to="checker",
    )
    quiet = ScriptedMonitor(trigger_kind=None)
    _first, _consult, resumed, received = run_consult_input(named)[:4]
    quiet_first, quiet_consult, quiet_resumed, quiet_received, _model = run_consult_input(quiet)
    print("named", None if resumed is None else resumed.committed_answer, TASK in received)
    print("quiet", quiet_first.consult_to, quiet_consult, quiet_resumed, quiet_received)


if __name__ == "__main__":
    main()
