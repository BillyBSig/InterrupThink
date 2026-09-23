from dataclasses import dataclass, field
from typing import Any, Literal

VerdictStatus = Literal["Unknown", "Ok", "Patch", "False"]
EventType = Literal[
    "thought.unit",
    "tool.intent",
    "answer.delta",
    "answer.commit",
    "monitor.verdict",
    "floor.cancel",
    "floor.rollback",
    "floor.inject",
    "floor.resume",
    "floor.escalate",
    "floor.consult",
    "floor.takeover",
]


@dataclass
class Patch:
    """Correction the specialist must use on the next request.

    The floor stores the patch and may include its fact in the resume
    prefix. The patch does not call ``run_session``.

    Attributes:
        from_agent: Name of the party that supplied the correction.
        target_unit_id: Step the correction answers.
        rollback_to: Last step that stays. ``None`` leaves the checkpoint
            to the floor.
        diagnosis: What was wrong.
        missing: Fact the next request must include.
        directive: Instruction for how to continue.
        preserve: Step identifiers that stay even when they sit after the
            checkpoint.
    """

    from_agent: str
    target_unit_id: str
    rollback_to: str | None
    diagnosis: str
    missing: str
    directive: str
    preserve: list[str] = field(default_factory=list)


@dataclass
class Verdict:
    """Decision for one ThoughtUnit.

    ``status`` is only ``Unknown``, ``Ok``, ``Patch``, or ``False``.
    A named handoff is not a fifth status: it stays ``Ok`` and fills
    exactly one of the route fields. ``Unknown`` does not open a route.
    A missing or blank route name does not route.

    Attributes:
        unit_id: Step this decision judges.
        status: ``Unknown``, ``Ok``, ``Patch``, or ``False``.
        reason: Short explanation recorded with the decision.
        patch: Correction required by ``Patch`` or ``False``.
        rollback_to: Checkpoint for a ``False`` decision.
        escalate_to: Next specialist. Set only with status ``Ok``.
        consult_to: Checker. Set only with status ``Ok``.
        takeover_to: Owner. Set only with status ``Ok``.
    """

    unit_id: str
    status: VerdictStatus
    reason: str = ""
    patch: Patch | None = None
    rollback_to: str | None = None
    escalate_to: str | None = None
    consult_to: str | None = None
    takeover_to: str | None = None


@dataclass
class RuntimeEvent:
    """One floor event and the payload recorded for it.

    Attributes:
        type: Event name, such as ``"floor.cancel"`` or ``"floor.consult"``.
        payload: Fields recorded for that event. The shape depends on
            ``type``.
    """

    type: EventType
    payload: dict[str, Any]
