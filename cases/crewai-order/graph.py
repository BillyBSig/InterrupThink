"""The counter role receives the host package. The crew does not kick off."""

from __future__ import annotations

from crewai import Agent, Crew, Process, Task

from interrupthink import Escalation, LiveLlm, ScriptedMonitor, Verdict, run_session


class OrderDesk:
    """Host desk. The menu check is stored on the call. Placement is refused here."""

    def __init__(self, order_result: str) -> None:
        self.calls: list[dict] = []
        self.order_result = order_result

    def execute(self, name: str, args: dict) -> str:
        if name == "place_order":
            result = "not placed"
        elif name == "read_order":
            result = self.order_result
        else:
            result = "ok"
        self.calls.append({"name": name, "args": dict(args), "result": result})
        return result


class OrderCrewResult:
    def __init__(self) -> None:
        self.first = None
        self.second = None
        self.package = ""
        self.counter_task = None
        self.counter_ran = False


def receiver_input(task: str, note: dict, role: str, reason: str) -> str:
    """Compose the counter's input from the imported package."""
    noted = dict(note)
    noted["escalate_to"] = role
    noted["reason"] = reason
    return Escalation.from_note(task, noted).text()


def compose_escalation(first, task: str, transcript: str, tool=None) -> tuple[str, set[str]]:
    """Build the package after the supervisor names counter."""
    if first.escalate_to != "counter":
        return "", set()
    note = next(event.payload for event in first.events if event.type == "floor.escalate")
    calls = [dict(call) for call in note["tool_calls"]]
    if tool is not None and not any(call["name"] == "read_order" for call in calls):
        tool.execute("read_order", {"transcript": transcript})
        calls.append(dict(tool.calls[-1]))
    note = {**note, "tool_calls": calls}
    composed = receiver_input(task, note, str(note["escalate_to"]), str(note.get("reason") or ""))
    return composed, {str(call["name"]) for call in calls}


def _block_place(written: set[str]):
    blocked = set(written)
    blocked.add("place_order")
    return lambda name, args: name not in blocked


class _OneEscalation:
    """Open counter once. A later claim that mentions counter stays put."""

    def __init__(self, inner: ScriptedMonitor) -> None:
        self.inner = inner
        self.opened = False

    def verdict(self, unit):
        if unit.kind == "claim" and "counter" in unit.text.casefold() and "\n" not in unit.text:
            if self.opened:
                return Verdict(unit_id=unit.id, status="Ok", reason="escalation already opened")
            self.opened = True
            return Verdict(
                unit_id=unit.id,
                status="Ok",
                reason="named specialist",
                escalate_to="counter",
            )
        return self.inner.verdict(unit)

    def __getattr__(self, name):
        return getattr(self.inner, name)


def live_task(task: str, transcript: str) -> str:
    return (
        task
        + "\n\nTranscript:\n"
        + transcript
        + "\n\nEmit only XML. Read the order, then one claim that asks counter, then an answer.\n"
        + "The order body is JSON on one line:\n"
        + '<step kind="tool_intent" reversible="true">'
        + '{"name":"read_order","args":{"transcript":"cone with bacon"}}</step>\n'
        + '<step kind="claim">ask counter</step>\n'
    )


def live_counter(composed: str) -> LiveLlm:
    """The counter role sees the package, including the menu result."""
    return LiveLlm(
        user_prompt=(
            composed
            + "\n\nEmit one claim and one answer. Do not emit tool_intent. "
            + "Use the menu result in the package. "
            + "If the order is not on the menu, say the cone with bacon is not on the menu."
        ),
        timeout_s=180.0,
    )


def run_order_crew(monitor, taker_llm, make_counter, desk, task: str, transcript: str) -> OrderCrewResult:
    """Two roles. The counter task receives the host package. The crew does not kick off."""
    result = OrderCrewResult()
    taker = Agent(
        role="Order Taker",
        goal="Read the transcript and stop before a mismatched order is placed.",
        backstory="You only read the written transcript.",
        allow_delegation=False,
        verbose=False,
    )
    counter = Agent(
        role="Counter",
        goal="Answer from the host package.",
        backstory="You do not take the route yourself.",
        allow_delegation=False,
        verbose=False,
    )
    taker_task = Task(description=transcript, expected_output="Order note.", agent=taker)
    counter_task = Task(
        description="Waiting for the host package.",
        expected_output="Menu decision.",
        agent=counter,
    )
    result.counter_task = counter_task
    Crew(
        agents=[taker, counter],
        tasks=[taker_task, counter_task],
        process=Process.sequential,
        verbose=False,
    )
    first = run_session(
        llm=taker_llm,
        monitor=monitor,
        tool=desk,
        tool_policy=lambda name, args: name != "place_order",
    )
    result.first = first
    if first.escalate_to != "counter":
        return result
    composed, written = compose_escalation(first, task, transcript, desk)
    result.package = composed
    counter_task.description = composed
    result.counter_ran = True
    result.second = run_session(
        llm=make_counter(composed),
        monitor=monitor,
        tool_policy=_block_place(written),
    )
    return result


def run_live_order(monitor: ScriptedMonitor, desk, task: str, transcript: str) -> OrderCrewResult:
    """Run the order taker and, when named, the counter role on the live model."""
    monitor = _OneEscalation(monitor)
    taker = LiveLlm(user_prompt=live_task(task, transcript), timeout_s=180.0)
    return run_order_crew(monitor, taker, live_counter, desk, task, transcript)
