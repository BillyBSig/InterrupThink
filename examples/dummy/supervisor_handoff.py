"""Host gives the named writer the task Agent A received, plus the kept work.

Scenario
    The writer sees the same task, the role the supervisor named, the
    supervisor's reason, the kept steps, and the tool calls that must not be
    repeated. The writer's first visible step is that package.

Expected
    Without a name, the writer receives nothing.
    With the name ``writer``, the first step contains the package, and
    ``write_note`` does not run again.

Usage (repo root; no API key)::

    pip install -e .
    python3 examples/dummy/supervisor_handoff.py
"""

from interrupthink import Escalation, FakeLlm, ScriptedMonitor, run_session

TASK = "Write the public release note."

HANDRAISE = """
tool_intent reversible: {"name":"write_note","args":{"text":"draft"}}
claim: this needs the writer
answer: I will finish the note myself.
"""


def writer_input(task: str, note: dict, role: str, reason: str) -> str:
    """Compose the next specialist's input from the imported package."""
    noted = dict(note)
    noted["escalate_to"] = role
    noted["reason"] = reason
    return Escalation.from_note(task, noted).text()


def _quoted_claim(text: str) -> str:
    """Keep a package inside one claim so later lines stay quoted context."""
    lines = text.splitlines() or [""]
    body = lines[0] + "".join(f"\n  {line}" for line in lines[1:])
    return f"claim: {body}"


def writer_document(composed: str) -> str:
    """The first visible step is the handoff. Angle brackets in the prefix are escaped."""
    visible = composed.replace("<", "[").replace(">", "]")
    tool = (
        'tool_intent reversible: ' '{"name":"write_note","args":{"text":"draft"}}'
    )
    return _quoted_claim(visible) + f"\n{tool}\nanswer: Wrote the note.\n"


def run_named_handoff(monitor: ScriptedMonitor):
    """Return the first result, the writer result, and the input the writer received."""
    first = run_session(llm=FakeLlm([HANDRAISE]), monitor=monitor)
    if first.escalate_to != "writer":
        return first, None, ""
    note = next(event.payload for event in first.events if event.type == "floor.escalate")
    reason = str(note.get("reason") or "")
    role = str(note["escalate_to"])
    composed = writer_input(TASK, note, role, reason)
    writer = FakeLlm([writer_document(composed)])
    writer.apply_resume(composed)
    written = {str(call["name"]) for call in note["tool_calls"]}
    second = run_session(
        llm=writer,
        monitor=monitor,
        tool_policy=lambda name, args: name not in written,
    )
    return first, second, writer.resume_envelope


def main() -> None:
    named = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="needs the writer",
        escalate_to="writer",
    )
    quiet = ScriptedMonitor(trigger_kind=None)
    _first, second, received = run_named_handoff(named)
    quiet_first, quiet_second, quiet_received = run_named_handoff(quiet)
    print("named", None if second is None else second.committed_answer)
    print("received", TASK in received)
    print("quiet", quiet_first.escalate_to, quiet_second, quiet_received)


if __name__ == "__main__":
    main()
