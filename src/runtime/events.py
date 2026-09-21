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
]


@dataclass
class Patch:
    from_agent: str
    target_unit_id: str
    rollback_to: str | None
    diagnosis: str
    missing: str
    directive: str
    preserve: list[str] = field(default_factory=list)


@dataclass
class Verdict:
    unit_id: str
    status: VerdictStatus
    reason: str = ""
    patch: Patch | None = None
    rollback_to: str | None = None


@dataclass
class RuntimeEvent:
    type: EventType
    payload: dict[str, Any]
