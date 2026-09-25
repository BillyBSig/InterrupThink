"""Host starts the next specialist only after the supervisor names them.

Scenario
    The first specialist asks for a writer. The monitor may name ``writer``.
    The host opens that session only when the name is present, and it reuses
    the same monitor. The first specialist does not call the second one.

Expected
    Without a name, only the first session runs.
    With the name ``writer``, the second session runs and is judged again.

Usage (repo root; no API key)::

    pip install -e .
    python3 examples/dummy/supervisor_escalation.py
"""

from interrupthink import FakeLlm, ScriptedMonitor, run_session

HANDRAISE = """
claim: this needs the writer
answer: I will finish the note myself.
"""

WRITER = """
claim: the note is ready for the reader
answer: Wrote the note.
"""


def run_named_escalation(monitor: ScriptedMonitor):
    """Return the first result and, only when named, the writer result."""
    first = run_session(llm=FakeLlm([HANDRAISE]), monitor=monitor)
    if first.escalate_to != "writer":
        return first, None
    second = run_session(llm=FakeLlm([WRITER]), monitor=monitor)
    return first, second


def main() -> None:
    named_monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="needs the writer",
        escalate_to="writer",
    )
    quiet_monitor = ScriptedMonitor(trigger_kind=None)
    named_first, named_second = run_named_escalation(named_monitor)
    quiet_first, quiet_second = run_named_escalation(quiet_monitor)
    print("named", named_first.escalate_to, None if named_second is None else named_second.committed_answer)
    print("quiet", quiet_first.escalate_to, quiet_second)


if __name__ == "__main__":
    main()
