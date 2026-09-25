"""Package text for a named receiver.

These objects compose the text a later specialist or a human reads.
They do not call ``run_session``.
"""

from __future__ import annotations


def _text(task: str, role: str, reason: str, prefix: str, tool_calls: list[dict]) -> str:
    """Compose the receiver's text from the host-owned fields.

    Args:
        task: Original task. It is not rewritten for the receiver.
        role: Name of the receiver.
        reason: Supervisor reason for the handoff.
        prefix: Kept steps. Dropped steps stay out.
        tool_calls: Calls that must not be repeated. A call with a
            ``result`` adds a ``result {name}: {result}`` line.

    Returns:
        The package as plain text. The last line names the calls that
        must not be repeated.
    """
    names = ", ".join(str(call["name"]) for call in tool_calls)
    lines = [task, f"role: {role}", f"reason: {reason}", prefix]
    for call in tool_calls:
        result = call.get("result")
        if result:
            lines.append(f"result {call['name']}: {result}")
    lines.append(f"do not repeat: {names}")
    return "\n".join(lines)


def _note_from_result(result, event_type: str) -> dict:
    """Return the payload of the first matching floor event.

    Args:
        result: Session result whose ``events`` are searched.
        event_type: Event name, such as ``"floor.consult"``.

    Returns:
        The event payload.

    Raises:
        ValueError: No event of that type is present.
    """
    for event in result.events:
        if event.type == event_type:
            return event.payload
    raise ValueError(f"missing {event_type}")


class _Package:
    """Shared package. Subclasses name the floor event and the role field.

    Attributes:
        task: Original task.
        role: Receiver named by the supervisor.
        reason: Supervisor reason.
        prefix: Kept steps.
        tool_calls: Tool calls copied from the handoff note.
        event_type: Floor event this subclass reads.
        role_field: Note field that carries the receiver's name.
    """

    event_type = ""
    role_field = ""

    def __init__(self, *, task: str, role: str, reason: str, prefix: str, tool_calls: list[dict]) -> None:
        """Store the fields the receiver will read.

        Args:
            task: Original task.
            role: Receiver name.
            reason: Supervisor reason.
            prefix: Kept steps.
            tool_calls: Calls that must not be repeated. The list is copied.
        """
        self.task = task
        self.role = role
        self.reason = reason
        self.prefix = prefix
        self.tool_calls = list(tool_calls)

    def text(self) -> str:
        """Return the package as plain text.

        Returns:
            Task, role, reason, kept prefix, tool results, and the calls
            that must not be repeated.
        """
        return _text(self.task, self.role, self.reason, self.prefix, self.tool_calls)

    @classmethod
    def from_note(cls, task: str, note: dict):
        """Build a package from a handoff note.

        Args:
            task: Original task. The note does not replace it.
            note: Payload from ``floor.consult``, ``floor.escalate``, or
                ``floor.takeover``.

        Returns:
            A package of this subclass.
        """
        return cls(
            task=task,
            role=str(note[cls.role_field]),
            reason=str(note.get("reason") or ""),
            prefix=str(note["prefix"]),
            tool_calls=list(note["tool_calls"]),
        )

    @classmethod
    def from_result(cls, task: str, result):
        """Build a package from the matching event on a session result.

        Args:
            task: Original task.
            result: Session result that contains this subclass's event.

        Returns:
            A package of this subclass.

        Raises:
            ValueError: The result has no event of this subclass's type.
        """
        return cls.from_note(task, _note_from_result(result, cls.event_type))


class Consult(_Package):
    """Package for the checker.

    The same specialist continues after the checker's answer comes back
    as a patch. This object only composes that checker's input.
    """

    event_type = "floor.consult"
    role_field = "consult_to"


class Escalation(_Package):
    """Package for the named specialist.

    The first specialist does not resume. The next specialist reads this
    package as a new request.
    """

    event_type = "floor.escalate"
    role_field = "escalate_to"


class Takeover(_Package):
    """Package for the named owner.

    ``editor`` is another specialist and may be given a new request.
    ``human`` is not a specialist: the host returns this text and does
    not open a second session.
    """

    event_type = "floor.takeover"
    role_field = "takeover_to"
