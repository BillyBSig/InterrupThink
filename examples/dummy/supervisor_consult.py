"""Host asks a checker, then returns that checked result to the same specialist.

Scenario
    The supervisor may name ``checker``. The host opens that session only when
    the name is present, and the same monitor judges it. The checked answer
    comes back as a patch. The original specialist continues. The owner does
    not move, and the checker's tool is not run again.

Expected
    Without a name, only the first session runs.
    With the name ``checker``, the original specialist finishes after the patch.

Usage (repo root; no API key)::

    pip install -e .
    python3 examples/dummy/supervisor_consult.py
"""

from interrupthink import FakeLlm, Patch, ScriptedMonitor, run_session

HANDRAISE = """
claim: ask the checker
answer: I will finish without a check.
"""

CHECKER = """
tool_intent reversible: {"name":"lookup_note","args":{"q":"draft"}}
claim: the note matches the draft
answer: The checker confirms the draft.
"""

CONTINUATION = """
tool_intent reversible: {"name":"lookup_note","args":{"q":"draft"}}
claim: the note can be finished
answer: Finished after the check.
"""


def run_named_consult(monitor: ScriptedMonitor):
    """Return the opening result, the checker result, and the same specialist resumed."""
    original = FakeLlm([HANDRAISE, CONTINUATION])
    first = run_session(llm=original, monitor=monitor)
    if first.consult_to != "checker":
        return first, None, None
    consult = run_session(llm=FakeLlm([CHECKER]), monitor=monitor)
    if consult.committed_answer is None:
        return first, consult, None
    note = next(event.payload for event in first.events if event.type == "floor.consult")
    patch = Patch(
        from_agent="A",
        target_unit_id=str(note["unit_id"]),
        rollback_to=None,
        diagnosis="consult",
        missing=consult.committed_answer,
        directive=consult.committed_answer,
    )
    written = {str(call["name"]) for call in consult.tool_calls}
    resumed = run_session(
        llm=original,
        monitor=monitor,
        resume_patch=patch,
        tool_policy=lambda name, args: name not in written,
    )
    return first, consult, resumed


def main() -> None:
    named = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="ask the checker",
        consult_to="checker",
    )
    quiet = ScriptedMonitor(trigger_kind=None)
    named_first, _consult, named_resumed = run_named_consult(named)
    quiet_first, quiet_consult, quiet_resumed = run_named_consult(quiet)
    print(
        "named",
        named_first.consult_to,
        None if named_resumed is None else named_resumed.committed_answer,
    )
    print("quiet", quiet_first.consult_to, quiet_consult, quiet_resumed)


if __name__ == "__main__":
    main()
