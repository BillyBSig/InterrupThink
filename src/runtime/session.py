from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from src.monitor.base import Monitor
from src.parse.assemble import StepAssembler, answer_text, is_answer_fragment
from src.parse.steps import ThoughtUnit, parse_steps
from src.providers.base import Llm
from src.providers.fake import DummyTool
from src.runtime.events import RuntimeEvent, Verdict
from src.runtime.floor import Floor, FloorAction
from src.runtime.log import JsonlLogger

ToolPolicy = Callable[[str, dict[str, Any]], bool]


class SessionError(RuntimeError):
    """Library session failed in a way the caller can fix (not a lab IndexError)."""


@dataclass
class SpikeResult:
    """Outcome of a 1:1 session.

    User-facing: committed_answer, interrupt_ids, dropped_ids, request_count, tool_calls.
    Other fields are diagnostic details and may evolve.
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


def run_session(
    *,
    llm: Llm,
    monitor: Monitor,
    tool: DummyTool | None = None,
    logger: JsonlLogger | None = None,
    execute_tools_when_ok: bool = True,
    tool_policy: ToolPolicy | None = None,
    max_requests: int = 4,
) -> SpikeResult:
    """Run one library session.

    The function does not rewrite ``llm.user_prompt``. Evaluation helpers live
    outside this library entry point.
    After interrupt, FakeLlm needs a second document or raises SessionError.
    ``tool_policy(name, args)`` is the host registry: False skips execute even
    if the model labeled the intent reversible and the monitor returned Ok.
    ``tool_policy=None`` is allow-if-Ok (demo/OSS), not production
    authorization. Consequential tools need an explicit policy.
    Exhausting ``max_requests`` without a completed request raises SessionError.
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
) -> SpikeResult:
    floor = Floor(rewrite_kept=rewrite_kept)
    events: list[RuntimeEvent] = []
    committed: str | None = None
    request_count = 0
    next_n = 1

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
            if aborted:
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
    )



def _apply_resume(llm, envelope: str | None) -> None:
    apply = getattr(llm, "apply_resume", None)
    if not callable(apply):
        raise SessionError(
            "llm has no apply_resume; resume envelope would be ignored"
        )
    apply(envelope)

def _iter_deltas(llm: Llm):
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
    payload = unit.tool or {}
    name = str(payload.get("name") or "unknown")
    args = dict(payload.get("args") or {})
    # None is allow-if-Ok. Default-deny needs a new decision record.
    if tool_policy is not None and not tool_policy(name, args):
        logger.write("tool.policy.deny", unit_id=unit.id, name=name, args=args)
        return
    tool.execute(name, args)
    logger.write("tool.execute", unit_id=unit.id, name=name, args=args)
