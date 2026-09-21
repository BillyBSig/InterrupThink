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
    abort: bool
    interrupt_id: str | None = None
    dropped_ids: list[str] = field(default_factory=list)
    events: list[RuntimeEvent] = field(default_factory=list)


class Floor:
    """Runtime owns cancel / rollback / inject. Models do not."""

    def __init__(self, *, rewrite_kept: Callable[[ThoughtUnit], bool] | None = None) -> None:
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
        """Hold a final answer until the request ends without abort."""
        self.pending_answer = text
        self.answer_state = "pending"
        self._answer_verdict_status = verdict.status

    def finalize_answer(self) -> str | None:
        """Commit to the protected sink only after an explicit Ok verdict."""
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
        self.pending_answer = None
        self._answer_verdict_status = None
        if self.answer_state == "pending":
            self.answer_state = "none"

    def ingest(self, unit: ThoughtUnit) -> None:
        if unit.id in self.dropped_ids:
            return
        self.units.append(unit)
        self.watermarks.speculative_head = unit.id

    def apply_verdict(self, verdict: Verdict) -> FloorAction:
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
        interrupt_id = f"int_{next(self._ids):02d}"
        self.interrupt_ids.append(interrupt_id)
        self.cancelled = True
        return interrupt_id

    def rollback(self, checkpoint_id: str, preserve: list[str] | None = None) -> list[str]:
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
        self.patches.append(patch)
        self._rewrite_wrong_spikes(patch)

    def binding_fact(self) -> str | None:
        if not self.patches:
            return None
        patch = self.patches[-1]
        text = (patch.missing or patch.directive or "").strip()
        return text or None

    def resume_prefix(self) -> str:
        """Kept steps only. Caller may rewrite kept units on inject; no overlay patch."""
        fact = self.binding_fact()
        parts: list[str] = []
        wrote_fact = False
        for unit in self.units:
            if unit.id in self.dropped_ids:
                continue
            parts.append(_unit_xml(unit))
            if fact and fact in unit.text:
                wrote_fact = True
        if fact and not wrote_fact:
            parts.append(_step_xml("premise", fact))
        return "\n".join(parts)

    def kept_texts(self) -> list[str]:
        return [u.text for u in self.units if u.id not in self.dropped_ids]

    def _rewrite_wrong_spikes(self, patch: Patch) -> None:
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
        for unit in self.units:
            if unit.id == unit_id:
                unit.state = "checked_ok"
                self.watermarks.checked_ok = unit_id
                return


def _unit_xml(unit: ThoughtUnit) -> str:
    extra = ""
    if unit.kind == "tool_intent" and unit.reversible is not None:
        extra = f' reversible="{str(unit.reversible).lower()}"'
    return _step_xml(unit.kind, unit.text, extra)


def _step_xml(kind: str, text: str, extra: str = "") -> str:
    return f'<step kind="{kind}"{extra}>{escape(text)}</step>'
