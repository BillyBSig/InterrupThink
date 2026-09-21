from __future__ import annotations

from src.runtime.events import Patch, Verdict
from src.parse.steps import ThoughtUnit


class ScriptedMonitor:
    """Deterministic monitor: Ok until a trigger step, then False + patch."""

    def __init__(
        self,
        *,
        trigger_kind: str | None = "premise",
        trigger_kinds: tuple[str, ...] | None = None,
        trigger_contains: str | None = None,
        rollback_to: str | None = None,
        patch: Patch | None = None,
        hold_irreversible_tool: bool = False,
    ) -> None:
        self.trigger_kind = trigger_kind
        self.trigger_kinds = trigger_kinds
        self.trigger_contains = trigger_contains
        self.rollback_to = rollback_to
        self.patch = patch
        self.hold_irreversible_tool = hold_irreversible_tool
        self.fired = False
        self.held_tool_ids: list[str] = []

    def verdict(self, unit: ThoughtUnit) -> Verdict:
        if (
            self.hold_irreversible_tool
            and unit.kind == "tool_intent"
            and unit.reversible is False
        ):
            self.held_tool_ids.append(unit.id)
            return Verdict(
                unit_id=unit.id,
                status="Unknown",
                reason="irreversible tool waits for Ok",
            )

        if self.fired:
            return Verdict(unit_id=unit.id, status="Ok", reason="scripted pass")

        if self._matches(unit):
            self.fired = True
            rollback_to = self.rollback_to or unit.parent_id
            patch = self.patch or Patch(
                from_agent="A",
                target_unit_id=unit.id,
                rollback_to=rollback_to,
                diagnosis="scripted interrupt",
                missing="corrected premise",
                directive="resume from checkpoint without dropped tail",
                preserve=[rollback_to] if rollback_to else [],
            )
            return Verdict(
                unit_id=unit.id,
                status="False",
                reason="scripted trigger",
                patch=patch,
                rollback_to=rollback_to,
            )

        return Verdict(unit_id=unit.id, status="Ok", reason="scripted pass")

    def release_tool(self, unit_id: str) -> Verdict:
        return Verdict(unit_id=unit_id, status="Ok", reason="tool gate released")

    def _matches(self, unit: ThoughtUnit) -> bool:
        kinds = self.trigger_kinds
        if kinds is None and self.trigger_kind is not None:
            kinds = (self.trigger_kind,)
        if kinds is None and self.trigger_contains is None:
            return False
        kind_ok = kinds is None or unit.kind in kinds
        text_ok = self.trigger_contains is None or self.trigger_contains in unit.text
        return kind_ok and text_ok
