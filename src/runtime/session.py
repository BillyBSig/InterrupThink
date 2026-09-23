from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from src.monitor.base import Monitor
from src.parse.assemble import StepAssembler, answer_text, is_answer_fragment
from src.parse.steps import ThoughtUnit, parse_steps
from src.providers.base import Llm
from src.providers.fake import DummyTool
from src.runtime.events import Patch, RuntimeEvent, Verdict
from src.runtime.floor import Floor, FloorAction
from src.runtime.log import JsonlLogger

ToolPolicy = Callable[[str, dict[str, Any]], bool]


class SessionError(RuntimeError):
    """The session stopped before it could finish.

    Raised when the specialist cannot accept a resume envelope, when a
    canned model has no document left for the next request, or when the
    request cap is exhausted before an answer is committed.
    """


@dataclass
class SpikeResult:
    """Outcome of one specialist session.

    ``committed_answer``, ``interrupt_ids``, ``dropped_ids``,
    ``request_count``, and ``tool_calls`` are the stable caller-facing
    fields. The other fields are diagnostic and may change.

    Attributes:
        path: Label stored on this result. The public entry uses
            ``"session"``.
        committed_answer: Answer text committed after ``Ok``. ``None``
            when the answer was held, rejected, or never offered.
        interrupt_ids: Cancel identifiers issued during the session.
        dropped_ids: Step identifiers removed by rollback.
        request_count: Specialist requests that were started.
        events: Floor and monitor events in order.
        log_records: Trace records written for this session.
        tool_calls: Tool calls the host executed.
        prefix: Kept steps prepared for a later request.
        watermarks: Checked step, speculative head, and committed answer.
        escalate_to: Next specialist, or ``""`` when no escalation opened.
        consult_to: Checker, or ``""`` when no consult opened.
        takeover_to: Owner, or ``""`` when no takeover opened.
    """

    path: str
    committed_answer: str | None
    interrupt_ids: list[str]
    dropped_ids: list[str]
    request_count: int
    events: list[RuntimeEvent] = field(default_factory=list)
    log_records: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    prefix: str = ""
    watermarks: dict[str, str | None] = field(default_factory=dict)
    escalate_to: str = ""
    consult_to: str = ""
    takeover_to: str = ""


def run_session(
    *,
    llm: Llm,
    monitor: Monitor,
    tool: DummyTool | None = None,
    logger: JsonlLogger | None = None,
    execute_tools_when_ok: bool = True,
    tool_policy: ToolPolicy | None = None,
    max_requests: int = 4,
    resume_patch: Patch | None = None,
) -> SpikeResult:
    """Run one specialist session.

    The function does not rewrite ``llm.user_prompt``. After a cut, the
    next request receives the kept prefix through ``apply_resume``. A
    canned model needs a second document for that request.

    ``tool_policy`` is the host registry. ``False`` skips the tool even
    when the model labeled it reversible and the monitor returned ``Ok``.
    ``None`` allows a tool after ``Ok``. A tool with a real effect needs
    an explicit policy.

    A named handoff stops the current specialist without committing the
    uncommitted answer. ``escalate_to``, ``consult_to``, or ``takeover_to``
    on the result names the receiver. The caller opens the next session.

    Args:
        llm: Specialist model for this session.
        monitor: Supervisor that judges each step.
        tool: Tool the host may execute. Defaults to a tool that records
            calls and returns ``"ok"``.
        logger: Trace writer. Defaults to an in-memory logger that redacts.
        execute_tools_when_ok: When false, an accepted tool intent is
            recorded and not executed.
        tool_policy: ``(name, args) -> bool``. ``False`` denies the call.
            ``None`` allows it after ``Ok``.
        max_requests: How many specialist requests this call may start.
        resume_patch: Correction applied before the first request when
            the caller is continuing a previous session.

    Returns:
        The session outcome, including any committed answer and any
        named receiver.

    Raises:
        SessionError: The model cannot accept a resume envelope, a canned
            model has no document for the next request, or ``max_requests``
            is exhausted before the session finishes.
    """
    logger = logger or JsonlLogger()
    tool = tool or DummyTool()
    return _run_session(
        "session",
        llm,
        monitor,
        tool,
        logger,
        execute_tools_when_ok=execute_tools_when_ok,
        tool_policy=tool_policy,
        max_requests=max_requests,
        resume_patch=resume_patch,
    )


def _run_session(
    path: str,
    llm: Llm,
    monitor: Monitor,
    tool: DummyTool,
    logger: JsonlLogger,
    *,
    execute_tools_when_ok: bool,
    rewrite_kept: Callable[[ThoughtUnit], bool] | None = None,
    lab_restart_prompt: Callable[[str, str], str] | None = None,
    lab_resume_prompt: Callable[[str, str], str] | None = None,
    tool_policy: ToolPolicy | None = None,
    max_requests: int = 4,
    resume_patch: Patch | None = None,
) -> SpikeResult:
    """Run the session loop used by ``run_session``.

    Args:
        path: Label stored on the result.
        llm: Specialist model.
        monitor: Supervisor for each step.
        tool: Tool the host may execute.
        logger: Trace writer.
        execute_tools_when_ok: Whether an accepted tool intent runs.
        rewrite_kept: Predicate passed to the floor for patch rewrites.
        lab_restart_prompt: Optional prompt builder. The public entry
            leaves this unset.
        lab_resume_prompt: Optional prompt builder. The public entry
            leaves this unset.
        tool_policy: Host allow function. ``None`` allows a tool after ``Ok``.
        max_requests: Request cap.
        resume_patch: Correction applied before the first request.

    Returns:
        The session outcome.

    Raises:
        SessionError: Resume cannot be applied, the model has no further
            document, or the request cap is exhausted.
    """
    floor = Floor(rewrite_kept=rewrite_kept)
    events: list[RuntimeEvent] = []
    committed: str | None = None
    request_count = 0
    next_n = 1
    escalated_to = ""
    consulted_to = ""
    taken_over_to = ""
    if resume_patch is not None:
        floor.inject(resume_patch)
        events.append(RuntimeEvent("floor.inject", {"patch": resume_patch.__dict__}))
        _apply_resume(llm, floor.resume_prefix())
        logger.write(
            "floor.inject",
            target_unit_id=resume_patch.target_unit_id,
            text=resume_patch.directive,
        )

    while request_count < max_requests:
        assembler = StepAssembler()
        request_count += 1
        aborted = False
        saw_step = False
        logger.write(
            "request.start",
            path=path,
            request_index=request_count,
            tokens=llm.tokens_emitted,
        )
        for delta in _iter_deltas(llm):
            for fragment in assembler.feed(delta):
                if is_answer_fragment(fragment):
                    action = _offer_answer_for_verdict(
                        answer_text(fragment),
                        floor,
                        monitor,
                        events,
                        logger,
                        next_n,
                    )
                    if action.abort:
                        llm.abort()
                        aborted = True
                        logger.write(
                            "floor.interrupt",
                            interrupt_id=action.interrupt_id,
                            dropped_ids=action.dropped_ids,
                            watermark=floor.watermarks.__dict__,
                            tokens_wasted=llm.tokens_wasted,
                            cancel_ok=getattr(llm, "cancel_ok", None),
                            response_id=getattr(llm, "response_id", None),
                        )
                        break
                    continue
                parsed = parse_steps(fragment, start_n=next_n)
                unit = parsed.units[0]
                if floor.units:
                    unit.parent_id = floor.units[-1].id
                saw_step = True
                action = _ingest_and_judge(
                    unit,
                    floor,
                    monitor,
                    tool,
                    logger,
                    events,
                    execute_tools_when_ok,
                    tool_policy,
                )
                next_n = int(unit.id.split("_")[1]) + 1
                if action.escalate_to:
                    llm.abort()
                    escalated_to = action.escalate_to
                    note = _escalate_note(action.escalate_to, unit.id, floor, tool)
                    for event in reversed(events):
                        if event.type == "monitor.verdict" and event.payload.get("escalate_to") == note["escalate_to"]:
                            note["reason"] = str(event.payload.get("reason") or "")
                            break
                    events.append(RuntimeEvent("floor.escalate", note))
                    logger.write(
                        "floor.escalate",
                        escalate_to=note["escalate_to"],
                        unit_id=note["unit_id"],
                        step_ids=note["step_ids"],
                        tool_calls=[call["name"] for call in note["tool_calls"]],
                        prefix=note["prefix"],
                        reason=note.get("reason", ""),
                    )
                    break
                if action.consult_to:
                    llm.abort()
                    consulted_to = action.consult_to
                    note = _consult_note(action.consult_to, unit.id, floor, tool)
                    for event in reversed(events):
                        if event.type == "monitor.verdict" and event.payload.get("consult_to") == note["consult_to"]:
                            note["reason"] = str(event.payload.get("reason") or "")
                            break
                    events.append(RuntimeEvent("floor.consult", note))
                    logger.write(
                        "floor.consult",
                        consult_to=note["consult_to"],
                        unit_id=note["unit_id"],
                        step_ids=note["step_ids"],
                        tool_calls=[call["name"] for call in note["tool_calls"]],
                        prefix=note["prefix"],
                        reason=note.get("reason", ""),
                    )
                    break
                if action.takeover_to:
                    llm.abort()
                    taken_over_to = action.takeover_to
                    note = _takeover_note(action.takeover_to, unit.id, floor, tool)
                    for event in reversed(events):
                        if event.type == "monitor.verdict" and event.payload.get("takeover_to") == note["takeover_to"]:
                            note["reason"] = str(event.payload.get("reason") or "")
                            break
                    events.append(RuntimeEvent("floor.takeover", note))
                    logger.write(
                        "floor.takeover",
                        takeover_to=note["takeover_to"],
                        unit_id=note["unit_id"],
                        step_ids=note["step_ids"],
                        tool_calls=[call["name"] for call in note["tool_calls"]],
                        prefix=note["prefix"],
                        reason=note.get("reason", ""),
                    )
                    break
                if action.abort:
                    llm.abort()
                    aborted = True
                    logger.write(
                        "floor.interrupt",
                        interrupt_id=action.interrupt_id,
                        dropped_ids=action.dropped_ids,
                        watermark=floor.watermarks.__dict__,
                        tokens_wasted=llm.tokens_wasted,
                        cancel_ok=getattr(llm, "cancel_ok", None),
                        response_id=getattr(llm, "response_id", None),
                    )
                    break
            if aborted or escalated_to or consulted_to or taken_over_to:
                break

        if escalated_to or consulted_to or taken_over_to:
            break

        if aborted:
            floor.drop_pending_answer()
            mode = getattr(llm, "resume_mode", "rollback")
            fact = floor.binding_fact()
            seed = getattr(llm, "trial_seed", None)
            if mode == "restart":
                _apply_resume(llm, None)
                if (
                    lab_restart_prompt
                    and fact
                    and seed is not None
                    and hasattr(llm, "user_prompt")
                ):
                    llm.user_prompt = lab_restart_prompt(str(seed), fact)
                logger.write(
                    "floor.resume",
                    mode="restart",
                    prefix="",
                    binding=fact,
                    request_next=request_count + 1,
                )
            else:
                prefix = floor.resume_prefix()
                _apply_resume(llm, prefix)
                if (
                    lab_resume_prompt
                    and fact
                    and seed is not None
                    and hasattr(llm, "user_prompt")
                ):
                    llm.user_prompt = lab_resume_prompt(str(seed), fact)
                logger.write(
                    "floor.resume",
                    mode="rollback",
                    prefix=prefix,
                    binding=fact,
                    request_next=request_count + 1,
                )
            continue

        for held_id in list(monitor.held_tool_ids):
            release = monitor.release_tool(held_id)
            floor.apply_verdict(release)
            logger.write("tool.gate.release", unit_id=held_id)
            held_unit = next((u for u in floor.units if u.id == held_id), None)
            if held_unit and execute_tools_when_ok:
                _maybe_execute_tool(held_unit, tool, logger, tool_policy)
            monitor.held_tool_ids.remove(held_id)

        approved = floor.finalize_answer()
        if approved:
            committed = approved
            events.append(RuntimeEvent("answer.commit", {"text": approved}))
            logger.write("answer.commit", text=approved)
        elif floor.answer_state == "rejected":
            events.append(RuntimeEvent("answer.rejected", {"status": "False"}))
            logger.write("answer.rejected", status="False")
        elif not saw_step:
            raise ValueError("llm produced no complete <step>")
        break
    else:
        raise SessionError(
            f"session exhausted request cap ({max_requests}) without a committed answer"
        )

    return SpikeResult(
        path=path,
        committed_answer=committed,
        interrupt_ids=list(floor.interrupt_ids),
        dropped_ids=sorted(floor.dropped_ids),
        request_count=request_count,
        events=events,
        log_records=list(logger.records),
        tool_calls=list(tool.calls),
        prefix=floor.resume_prefix(),
        watermarks=dict(floor.watermarks.__dict__),
        escalate_to=escalated_to,
        consult_to=consulted_to,
        takeover_to=taken_over_to,
    )



def _handoff_note(field: str, name: str, unit_id: str, floor, tool) -> dict:
    """Build the note a named receiver will read.

    Args:
        field: Route field, such as ``"escalate_to"``.
        name: Receiver name.
        unit_id: Step that opened the route.
        floor: Floor that supplies the kept prefix.
        tool: Tool whose calls are copied onto the note.

    Returns:
        The receiver name, the triggering step, the kept prefix, the
        kept step identifiers, and a copy of the tool calls.
    """
    return {
        field: name,
        "unit_id": unit_id,
        "prefix": floor.resume_prefix(),
        "step_ids": [unit.id for unit in floor.units if unit.id not in floor.dropped_ids],
        "tool_calls": [dict(call) for call in tool.calls],
    }


def _escalate_note(name: str, unit_id: str, floor, tool) -> dict:
    """Build the note for the next specialist.

    Args:
        name: Specialist who receives the rest of the task.
        unit_id: Step that opened the escalation.
        floor: Floor that supplies the kept prefix.
        tool: Tool whose calls are copied onto the note.

    Returns:
        A handoff note whose route field is ``escalate_to``.
    """
    return _handoff_note("escalate_to", name, unit_id, floor, tool)


def _consult_note(name: str, unit_id: str, floor, tool) -> dict:
    """Build the note for the checker.

    Args:
        name: Checker who should answer.
        unit_id: Step that opened the consult.
        floor: Floor that supplies the kept prefix.
        tool: Tool whose calls are copied onto the note.

    Returns:
        A handoff note whose route field is ``consult_to``.
    """
    return _handoff_note("consult_to", name, unit_id, floor, tool)


def _takeover_note(name: str, unit_id: str, floor, tool) -> dict:
    """Build the note for the owner.

    Args:
        name: Owner who receives the task. ``"human"`` is not a specialist.
        unit_id: Step that opened the takeover.
        floor: Floor that supplies the kept prefix.
        tool: Tool whose calls are copied onto the note.

    Returns:
        A handoff note whose route field is ``takeover_to``.
    """
    return _handoff_note("takeover_to", name, unit_id, floor, tool)


def _apply_resume(llm, envelope: str | None) -> None:
    """Give the model the text for its next request.

    Args:
        llm: Specialist model. It must implement ``apply_resume``.
        envelope: Resume prefix. ``None`` clears a stored prefix.

    Raises:
        SessionError: The model has no ``apply_resume`` method.
    """
    apply = getattr(llm, "apply_resume", None)
    if not callable(apply):
        raise SessionError(
            "llm has no apply_resume; resume envelope would be ignored"
        )
    apply(envelope)

def _iter_deltas(llm: Llm):
    """Yield the specialist text for the current request.

    Args:
        llm: Specialist model. ``iter_deltas`` is used when present.
            Otherwise the full ``generate`` string is yielded once.

    Yields:
        Text chunks from the model.

    Raises:
        SessionError: A canned model has no document left for this request.
    """
    iterator = getattr(llm, "iter_deltas", None)
    try:
        if callable(iterator):
            yield from iterator()
            return
        yield llm.generate()
    except IndexError as exc:
        raise SessionError(
            "llm has no further output for this request; "
            "after an interrupt, FakeLlm needs a second XML document"
        ) from exc


def _offer_answer_for_verdict(text, floor, monitor, events, logger, next_n) -> FloorAction:
    """Ask the monitor to judge a proposed answer before it can commit.

    Args:
        text: Answer text.
        floor: Floor that will hold the answer.
        monitor: Supervisor that judges the answer draft.
        events: Event list that receives the verdict event.
        logger: Trace writer.
        next_n: Number used in the draft step identifier.

    Returns:
        The floor action for that verdict. The answer stays pending
        until the session finalizes it.
    """
    parent = floor.units[-1].id if floor.units else ""
    unit = ThoughtUnit(
        id=f"u_{next_n:02d}",
        agent="B",
        parent_id=parent,
        kind="answer_draft",
        text=text,
        state="pending",
    )
    verdict = monitor.verdict(unit)
    events.append(RuntimeEvent("monitor.verdict", {"status": verdict.status, "unit_id": unit.id}))
    logger.write(
        "monitor.verdict",
        unit_id=unit.id,
        status=verdict.status,
        reason=verdict.reason,
    )
    if verdict.status in ("False", "Patch"):
        if verdict.status == "False":
            rollback_to = verdict.rollback_to or floor.watermarks.checked_ok
            if rollback_to is None and floor.units:
                rollback_to = floor.units[-1].id
            if rollback_to is None:
                # No checkpoint: hold. Do not abort into a resume without an anchor.
                floor.offer_answer(text, verdict)
                return FloorAction(abort=False)
            if rollback_to != verdict.rollback_to:
                verdict = Verdict(
                    unit_id=verdict.unit_id,
                    status=verdict.status,
                    reason=verdict.reason,
                    patch=verdict.patch,
                    rollback_to=rollback_to,
                )
        action = floor.apply_verdict(verdict)
        events.extend(action.events)
        return action
    floor.offer_answer(text, verdict)
    return FloorAction(abort=False)


def _ingest_and_judge(
    unit, floor, monitor, tool, logger, events, execute_tools_when_ok, tool_policy=None
):
    """Record one step, judge it, and maybe execute its tool.

    Args:
        unit: Step to ingest.
        floor: Floor that stores the step.
        monitor: Supervisor that judges it.
        tool: Tool that may run for a tool step.
        logger: Trace writer.
        events: Event list for the step and the verdict.
        execute_tools_when_ok: Whether an accepted tool step may run.
        tool_policy: Host allow function. ``None`` allows the tool after ``Ok``.

    Returns:
        The floor action for the verdict. A named route aborts the
        request without resuming the same specialist.
    """
    floor.ingest(unit)
    events.append(RuntimeEvent("thought.unit", {"id": unit.id, "kind": unit.kind}))
    logger.write(
        "thought.unit",
        unit_id=unit.id,
        kind=unit.kind,
        text=unit.text,
        watermark=floor.watermarks.__dict__,
    )
    if unit.kind == "tool_intent":
        events.append(
            RuntimeEvent(
                "tool.intent",
                {
                    "unit_id": unit.id,
                    "name": (unit.tool or {}).get("name"),
                    "reversible": unit.reversible,
                },
            )
        )
    verdict = monitor.verdict(unit)
    named = (verdict.escalate_to or "").strip()
    consulted = (verdict.consult_to or "").strip()
    taken = (verdict.takeover_to or "").strip()
    # Unknown never routes. A name on any other explicit verdict ends this session.
    if named and verdict.status != "Unknown":
        events.append(
            RuntimeEvent(
                "monitor.verdict",
                {
                    "status": verdict.status,
                    "unit_id": unit.id,
                    "escalate_to": named,
                    "reason": verdict.reason,
                },
            )
        )
        logger.write(
            "monitor.verdict",
            unit_id=unit.id,
            status=verdict.status,
            reason=verdict.reason,
            escalate_to=named,
        )
        return FloorAction(abort=False, escalate_to=named)
    if consulted and verdict.status != "Unknown":
        events.append(
            RuntimeEvent(
                "monitor.verdict",
                {
                    "status": verdict.status,
                    "unit_id": unit.id,
                    "consult_to": consulted,
                    "reason": verdict.reason,
                },
            )
        )
        logger.write(
            "monitor.verdict",
            unit_id=unit.id,
            status=verdict.status,
            reason=verdict.reason,
            consult_to=consulted,
        )
        return FloorAction(abort=False, consult_to=consulted)
    if taken and verdict.status != "Unknown":
        events.append(
            RuntimeEvent(
                "monitor.verdict",
                {
                    "status": verdict.status,
                    "unit_id": unit.id,
                    "takeover_to": taken,
                    "reason": verdict.reason,
                },
            )
        )
        logger.write(
            "monitor.verdict",
            unit_id=unit.id,
            status=verdict.status,
            reason=verdict.reason,
            takeover_to=taken,
        )
        return FloorAction(abort=False, takeover_to=taken)
    events.append(RuntimeEvent("monitor.verdict", {"status": verdict.status, "unit_id": unit.id}))
    logger.write(
        "monitor.verdict",
        unit_id=unit.id,
        status=verdict.status,
        reason=verdict.reason,
    )
    action = floor.apply_verdict(verdict)
    events.extend(action.events)
    if verdict.status == "Ok" and unit.kind == "tool_intent" and execute_tools_when_ok:
        _maybe_execute_tool(unit, tool, logger, tool_policy)
    return action


def _maybe_execute_tool(
    unit, tool: DummyTool, logger: JsonlLogger, tool_policy: ToolPolicy | None = None
) -> None:
    """Execute a tool step unless the host policy denies it.

    Args:
        unit: Tool step. Its parsed body supplies the name and arguments.
        tool: Tool implementation.
        logger: Trace writer. A denial is recorded as ``tool.policy.deny``.
        tool_policy: ``(name, args) -> bool``. ``None`` allows the call.
            ``False`` skips ``execute``.
    """
    payload = unit.tool or {}
    name = str(payload.get("name") or "unknown")
    args = dict(payload.get("args") or {})
    # None is allow-if-Ok. Default-deny needs a new decision record.
    if tool_policy is not None and not tool_policy(name, args):
        logger.write("tool.policy.deny", unit_id=unit.id, name=name, args=args)
        return
    tool.execute(name, args)
    logger.write("tool.execute", unit_id=unit.id, name=name, args=args)
