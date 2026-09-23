"""Deterministic supervisor used by tests and scripted hosts."""

from __future__ import annotations

from src.runtime.events import Patch, Verdict
from src.parse.steps import ThoughtUnit


class ScriptedMonitor:
    """Judge steps with a fixed rule instead of calling a model.

    Use this monitor in tests and in hosts that already know which step
    should cut. A live supervisor belongs on ``LlmMonitor``.

    The first matching route wins. ``escalate_to`` is checked before
    ``consult_to``, and ``consult_to`` before ``takeover_to``. A named
    route returns ``Ok`` together with that name. A blank name is stored
    as ``None`` and does not route. A matching step whose text contains a
    newline is quoted context: the verdict stays ``Ok`` and the route
    does not open.

    When no route name is set, the first match returns ``False`` and a
    ``Patch``. ``fired`` then stays true and later steps pass. An
    irreversible tool step can be held as ``Unknown`` before those rules
    run.

    Attributes:
        trigger_kind: Step kind that can match. Ignored when
            ``trigger_kinds`` is set. ``None`` does not filter by kind.
        trigger_kinds: Kinds that replace ``trigger_kind`` when set.
        trigger_contains: Substring that must appear in the step text.
            ``None`` does not filter by text.
        rollback_to: Checkpoint for the ``False`` path. The matching
            step's parent is used when this is omitted.
        patch: Correction returned with ``False``. A small default
            correction is used when this is omitted.
        hold_irreversible_tool: When true, an irreversible tool step is
            held as ``Unknown`` until ``release_tool``.
        escalate_to: Specialist who should receive the rest of the task.
            ``None`` does not open an escalation.
        consult_to: Checker who should answer and return a patch to the
            same specialist. ``None`` does not open a consult.
        takeover_to: Owner who should receive the task. ``None`` does not
            open a takeover.
        fired: Whether the unnamed ``False`` path has already fired.
            Named routes do not set this.
        held_tool_ids: Identifiers of tool steps returned as ``Unknown``.

    Examples:
        Cut when a premise says the freeze is over::

            monitor = ScriptedMonitor(
                trigger_kind="premise",
                trigger_contains="freeze is over",
            )
    """

    def __init__(
        self,
        *,
        trigger_kind: str | None = "premise",
        trigger_kinds: tuple[str, ...] | None = None,
        trigger_contains: str | None = None,
        rollback_to: str | None = None,
        patch: Patch | None = None,
        hold_irreversible_tool: bool = False,
        escalate_to: str | None = None,
        consult_to: str | None = None,
        takeover_to: str | None = None,
    ) -> None:
        """Store the trigger and the optional named route.

        Args:
            trigger_kind: Kind that can fire the trigger. Defaults to
                ``"premise"``. Pass ``None`` to ignore kind.
            trigger_kinds: Kinds that replace ``trigger_kind`` when given.
            trigger_contains: Substring required in the step text.
            rollback_to: Checkpoint for the ``False`` path.
            patch: Correction attached to a ``False`` verdict.
            hold_irreversible_tool: Hold irreversible tool steps as
                ``Unknown`` instead of judging them as ordinary steps.
            escalate_to: Name of the next specialist. Blank becomes
                ``None``.
            consult_to: Name of the checker. Blank becomes ``None``.
            takeover_to: Name of the owner. Blank becomes ``None``.
        """
        self.trigger_kind = trigger_kind
        self.trigger_kinds = trigger_kinds
        self.trigger_contains = trigger_contains
        self.rollback_to = rollback_to
        self.patch = patch
        self.hold_irreversible_tool = hold_irreversible_tool
        self.escalate_to = (escalate_to or "").strip() or None
        self.consult_to = (consult_to or "").strip() or None
        self.takeover_to = (takeover_to or "").strip() or None
        self.fired = False
        self.held_tool_ids: list[str] = []

    def verdict(self, unit: ThoughtUnit) -> Verdict:
        """Judge one step against the stored rule.

        An irreversible tool is held first when that option is on. After
        the unnamed trigger has fired, later steps pass. A named route is
        considered before the ``False`` path.

        Args:
            unit: Step produced by the specialist.

        Returns:
            ``Unknown`` while an irreversible tool is held. ``Ok`` with
            ``escalate_to``, ``consult_to``, or ``takeover_to`` when a
            named route opens. ``False`` and a patch when the unnamed
            trigger matches. ``Ok`` for every other step.
        """
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
            if self.escalate_to:
                if "\n" in unit.text:
                    return Verdict(unit_id=unit.id, status="Ok", reason="quoted context")
                return Verdict(
                    unit_id=unit.id,
                    status="Ok",
                    reason="named specialist",
                    escalate_to=self.escalate_to,
                )
            if self.consult_to:
                if "\n" in unit.text:
                    return Verdict(unit_id=unit.id, status="Ok", reason="quoted context")
                return Verdict(
                    unit_id=unit.id,
                    status="Ok",
                    reason="named consult",
                    consult_to=self.consult_to,
                )
            if self.takeover_to:
                if "\n" in unit.text:
                    return Verdict(unit_id=unit.id, status="Ok", reason="quoted context")
                return Verdict(
                    unit_id=unit.id,
                    status="Ok",
                    reason="named owner",
                    takeover_to=self.takeover_to,
                )
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
        """Allow a previously held tool step to proceed.

        Args:
            unit_id: Identifier of the held tool step.

        Returns:
            An ``Ok`` verdict for that identifier. The monitor does not
            remove the identifier from ``held_tool_ids``.
        """
        return Verdict(unit_id=unit_id, status="Ok", reason="tool gate released")

    def _matches(self, unit: ThoughtUnit) -> bool:
        """Return whether this step is the configured trigger.

        Args:
            unit: Step to test.

        Returns:
            True when the kind filter and the text filter both pass.
            False when neither filter is configured.
        """
        kinds = self.trigger_kinds
        if kinds is None and self.trigger_kind is not None:
            kinds = (self.trigger_kind,)
        if kinds is None and self.trigger_contains is None:
            return False
        kind_ok = kinds is None or unit.kind in kinds
        text_ok = self.trigger_contains is None or self.trigger_contains in unit.text
        return kind_ok and text_ok
