from __future__ import annotations

from typing import Protocol

from interrupthink.parse.steps import ThoughtUnit
from interrupthink.runtime.events import Verdict


class Monitor(Protocol):
    """Supervisor that judges one step and can release a held tool.

    ``Unknown`` is the neutral result. A monitor must not turn a missing
    or malformed judgment into ``False``.

    Attributes:
        held_tool_ids: Identifiers of tool steps the monitor is holding.
    """

    held_tool_ids: list[str]

    def verdict(self, unit: ThoughtUnit) -> Verdict:
        """Judge one step.

        Args:
            unit: Step produced by the specialist.

        Returns:
            A verdict whose status is ``Unknown``, ``Ok``, ``Patch``, or
            ``False``. A named handoff uses ``Ok`` plus one route field.
        """
        ...

    def release_tool(self, unit_id: str) -> Verdict:
        """Allow a held tool step to proceed.

        Args:
            unit_id: Identifier of the held tool step.

        Returns:
            An ``Ok`` verdict for that identifier.
        """
        ...
