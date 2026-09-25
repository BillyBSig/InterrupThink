from __future__ import annotations

import itertools
from collections.abc import Callable
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

from src.parse.steps import ThoughtUnit
from src.runtime.events import Patch, RuntimeEvent, Verdict
from src.runtime.watermark import Watermarks


@dataclass
class FloorAction:
    """Result of applying one verdict to the current request.

    ``abort`` stops that request. The session fills a named handoff when
    the monitor accepted one; ``Floor.apply_verdict`` itself only handles
    ``Unknown``, ``Ok``, ``Patch``, and ``False``.

    Attributes:
        abort: Whether the current specialist request must stop.
        interrupt_id: Identifier recorded for a cancel, if one happened.
        dropped_ids: Step identifiers removed by rollback.
        events: Floor events produced while applying the verdict.
        escalate_to: Next specialist, when the session opened an escalation.
        consult_to: Checker, when the session opened a consult.
        takeover_to: Owner, when the session opened a takeover.
    """

    abort: bool
    interrupt_id: str | None = None
    dropped_ids: list[str] = field(default_factory=list)
    events: list[RuntimeEvent] = field(default_factory=list)
    escalate_to: str | None = None
    consult_to: str | None = None
    takeover_to: str | None = None


class Floor:
    """Owns cancel, rollback, and inject for one specialist request.

    The model emits steps. This object decides which of those steps stay,
    which answer may be committed, and what text a later request may see.
    A resume prefix contains kept steps only. Dropped steps and an
    uncommitted answer stay out.

    Attributes:
        units: Steps accepted into this request, including ones later marked
            dropped.
        dropped_ids: Identifiers removed by rollback.
        patches: Corrections stored by ``inject``, oldest first.
        watermarks: Last checked step, speculative head, and committed answer.
        interrupt_ids: Cancel identifiers issued by this floor.
        cancelled: Whether the current request has been cancelled.
        rewrite_kept: Optional predicate. A matching kept step is rewritten
            with the latest patch fact.
        pending_answer: Answer waiting for ``finalize_answer``.
        answer_state: ``"none"``, ``"pending"``, ``"approved"``,
            ``"rejected"``, or ``"held"``.
    """

    def __init__(self, *, rewrite_kept: Callable[[ThoughtUnit], bool] | None = None) -> None:
        """Start an empty floor.

        Args:
            rewrite_kept: Predicate that selects kept steps whose text
                should be replaced when a patch is injected. ``None``
                leaves kept text unchanged.
        """
        self.units: list[ThoughtUnit] = []
        self.dropped_ids: set[str] = set()
        self.patches: list[Patch] = []
        self.watermarks = Watermarks()
        self.interrupt_ids: list[str] = []
        self.cancelled = False
        self._ids = itertools.count(1)
        self.rewrite_kept = rewrite_kept
        self.pending_answer: str | None = None
        self.answer_state: str = "none"
        self._answer_verdict_status: str | None = None

    def offer_answer(self, text: str, verdict: Verdict) -> None:
        """Hold a final answer until the request ends without abort.

        Args:
            text: Answer text proposed by the specialist.
            verdict: Verdict already given for that answer.
        """
        self.pending_answer = text
        self.answer_state = "pending"
        self._answer_verdict_status = verdict.status

    def finalize_answer(self) -> str | None:
        """Commit a held answer only after an explicit ``Ok``.

        Returns:
            The answer text when its verdict was ``Ok``. ``None`` when
            there is no pending answer, or when the verdict was ``False``,
            ``Unknown``, or ``Patch``. ``False`` marks the answer rejected.
            The other non-``Ok`` statuses mark it held.
        """
        pending = self.pending_answer
        status = self._answer_verdict_status
        self.pending_answer = None
        self._answer_verdict_status = None
        if pending is None:
            self.answer_state = "none"
            return None
        if status == "Ok":
            self.answer_state = "approved"
            self.watermarks.committed_answer = pending
            return pending
        if status == "False":
            self.answer_state = "rejected"
        else:
            self.answer_state = "held"
        return None

    def drop_pending_answer(self) -> None:
        """Discard an answer that has not been committed.

        A pending answer returns to ``"none"``. An answer already approved,
        rejected, or held keeps that state.
        """
        self.pending_answer = None
        self._answer_verdict_status = None
        if self.answer_state == "pending":
            self.answer_state = "none"

    def ingest(self, unit: ThoughtUnit) -> None:
        """Record a step and move the speculative head.

        Args:
            unit: Step to keep. An identifier already in ``dropped_ids``
                is ignored.
        """
        if unit.id in self.dropped_ids:
            return
        self.units.append(unit)
        self.watermarks.speculative_head = unit.id

    def apply_verdict(self, verdict: Verdict) -> FloorAction:
        """Apply one status to the current request.

        ``Ok`` marks the step checked and continues. ``Unknown`` continues
        without moving the checked watermark. ``Patch`` aborts the request
        and stores the correction. ``False`` aborts, drops the tail after
        the checkpoint, and stores a patch when one is present.

        Args:
            verdict: Decision for the current step.

        Returns:
            An action whose ``abort`` flag tells the session to stop the
            current specialist request.

        Raises:
            ValueError: ``Patch`` has no patch payload, ``False`` has no
                checkpoint, or ``status`` is not one of the four verdict
                statuses.
        """
        if verdict.status in ("Unknown", "Ok"):
            if verdict.status == "Ok":
                self._mark_ok(verdict.unit_id)
            return FloorAction(abort=False)

        if verdict.status == "Patch":
            if verdict.patch is None:
                raise ValueError("Patch verdict requires patch payload")
            self.inject(verdict.patch)
            interrupt_id = self.cancel(verdict.reason or "monitor.Patch")
            return FloorAction(
                abort=True,
                interrupt_id=interrupt_id,
                events=[
                    RuntimeEvent("floor.inject", {"patch": verdict.patch.__dict__}),
                    RuntimeEvent(
                        "floor.cancel",
                        {"interrupt_id": interrupt_id, "reason": verdict.reason},
                    ),
                ],
            )

        if verdict.status != "False":
            raise ValueError(f"unknown verdict status: {verdict.status}")

        rollback_to = verdict.rollback_to or self.watermarks.checked_ok
        if rollback_to is None:
            raise ValueError("False verdict needs rollback_to or checked_ok watermark")

        interrupt_id = self.cancel(verdict.reason or "monitor.False")
        dropped = self.rollback(rollback_to, preserve=verdict.patch.preserve if verdict.patch else [])
        if verdict.patch:
            self.inject(verdict.patch)
        events = [
            RuntimeEvent("floor.cancel", {"interrupt_id": interrupt_id, "reason": verdict.reason}),
            RuntimeEvent(
                "floor.rollback",
                {"checkpoint_id": rollback_to, "drop_unit_ids": dropped},
            ),
        ]
        if verdict.patch:
            events.append(RuntimeEvent("floor.inject", {"patch": verdict.patch.__dict__}))
        events.append(
            RuntimeEvent("floor.resume", {"prefix_watermark": rollback_to}),
        )
        return FloorAction(
            abort=True,
            interrupt_id=interrupt_id,
            dropped_ids=dropped,
            events=events,
        )

    def cancel(self, reason: str) -> str:
        """Record an interrupt id and mark the current request cancelled.

        Args:
            reason: Why the request stopped. The reason is not stored on
                the floor; the caller records it on the cancel event.

        Returns:
            A new interrupt identifier, such as ``"int_01"``.
        """
        interrupt_id = f"int_{next(self._ids):02d}"
        self.interrupt_ids.append(interrupt_id)
        self.cancelled = True
        return interrupt_id

    def rollback(self, checkpoint_id: str, preserve: list[str] | None = None) -> list[str]:
        """Drop steps after the checkpoint.

        The checkpoint itself stays. Steps listed in ``preserve`` also
        stay, even when they sit after the checkpoint. The checked
        watermark moves to the checkpoint.

        Args:
            checkpoint_id: Last step that must remain.
            preserve: Extra step identifiers that must remain.

        Returns:
            Identifiers of the steps that were dropped, in their original
            order.
        """
        keep_preserve = set(preserve or [])
        dropped: list[str] = []
        past_checkpoint = False
        kept: list[ThoughtUnit] = []
        for unit in self.units:
            if unit.id == checkpoint_id:
                past_checkpoint = True
                kept.append(unit)
                continue
            if past_checkpoint and unit.id not in keep_preserve:
                unit.state = "rejected"
                self.dropped_ids.add(unit.id)
                dropped.append(unit.id)
            else:
                kept.append(unit)
        self.units = kept
        self.watermarks.checked_ok = checkpoint_id
        self.watermarks.speculative_head = kept[-1].id if kept else None
        return dropped

    def inject(self, patch: Patch) -> None:
        """Store a patch and rewrite kept steps when a matcher is set.

        Args:
            patch: Correction to keep. The latest patch supplies
                ``binding_fact``.
        """
        self.patches.append(patch)
        self._rewrite_wrong_spikes(patch)

    def binding_fact(self) -> str | None:
        """Return the latest patch fact.

        Returns:
            ``missing`` from the latest patch, or ``directive`` when
            ``missing`` is blank. ``None`` when no patch is stored or
            both fields are blank.
        """
        if not self.patches:
            return None
        patch = self.patches[-1]
        text = (patch.missing or patch.directive or "").strip()
        return text or None

    def resume_prefix(self) -> str:
        """Serialize the steps a later request may see.

        Dropped steps are omitted. When the latest patch fact is not
        already inside a kept step, it is appended as one premise.
        Inject rewrites kept text in place; this method does not overlay
        a second copy of the patch.

        Returns:
            Plain lines for the kept steps, separated by newlines. An empty
            string when nothing was kept and there is no patch fact.
        """
        fact = self.binding_fact()
        parts: list[str] = []
        wrote_fact = False
        for unit in self.units:
            if unit.id in self.dropped_ids:
                continue
            parts.append(_unit_line(unit))
            if fact and fact in unit.text:
                wrote_fact = True
        if fact and not wrote_fact:
            parts.append(f"premise: {fact}")
        return "\n".join(parts)

    def kept_texts(self) -> list[str]:
        """Return the text of steps that were not dropped.

        Returns:
            Texts in floor order. Dropped steps are absent.
        """
        return [u.text for u in self.units if u.id not in self.dropped_ids]

    def _rewrite_wrong_spikes(self, patch: Patch) -> None:
        """Replace kept step text when ``rewrite_kept`` matches.

        Args:
            patch: Correction whose fact replaces the matched text.
        """
        matcher = self.rewrite_kept
        if matcher is None:
            return
        fact = (patch.missing or patch.directive or "").strip()
        if not fact:
            return
        for unit in self.units:
            if unit.id in self.dropped_ids:
                continue
            if matcher(unit):
                unit.text = fact

    def _mark_ok(self, unit_id: str) -> None:
        """Mark one step checked and move the checked watermark.

        Args:
            unit_id: Identifier of the step that received ``Ok``.
        """
        for unit in self.units:
            if unit.id == unit_id:
                unit.state = "checked_ok"
                self.watermarks.checked_ok = unit_id
                return


def _unit_line(unit: ThoughtUnit) -> str:
    """Serialize one kept step as a plain line.

    Args:
        unit: Step to serialize.

    Returns:
        One ``kind: text`` line. A reversible tool uses
        ``tool_intent reversible:``.
    """
    text = " ".join(unit.text.split())
    if unit.kind == "tool_intent" and unit.reversible:
        return f"tool_intent reversible: {text}"
    return f"{unit.kind}: {text}"


def _unit_xml(unit: ThoughtUnit) -> str:
    """Serialize one kept step, including a reversible attribute for tools.

    Args:
        unit: Step to serialize.

    Returns:
        One escaped ``<step>`` element.
    """
    extra = ""
    if unit.kind == "tool_intent" and unit.reversible is not None:
        extra = f' reversible="{str(unit.reversible).lower()}"'
    return _step_xml(unit.kind, unit.text, extra)


def _step_xml(kind: str, text: str, extra: str = "") -> str:
    """Serialize one step element with escaped text.

    Args:
        kind: Step kind written into the tag.
        text: Step body. XML metacharacters are escaped.
        extra: Extra attributes already formatted, such as
            `` reversible="true"``.

    Returns:
        One ``<step>`` element.
    """
    return f'<step kind="{kind}"{extra}>{escape(text)}</step>'
