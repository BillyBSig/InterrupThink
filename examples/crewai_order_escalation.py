"""The counter role receives the order package, and the wrong order is not placed.

Scenario
    The host has a written transcript, not a microphone. The order taker reads
    it. The supervisor names ``counter`` before a mismatched order is committed.
    The counter role sees the package. The crew does not choose that route.

Expected
    ``place_order`` does not run for the mismatched order.
    The order taker does not commit it. The counter answers from the menu result.

Usage (repo root)::

    pip install -e . && pip install crewai   # venv; do not uv-add
    python3 examples/crewai_order_escalation.py

Cookbook: ``cases/crewai-order/run.py``.
"""

from __future__ import annotations

import os
from pathlib import Path

from crewai import Agent, Crew, Process, Task

from interrupthink import Escalation, LiveLlm, ScriptedMonitor, Verdict, run_session

TASK = "Read the order transcript and place an order only when it is on the menu."
TRANSCRIPT = "Customer: a cone with bacon."
ORDER_RESULT = "cone with bacon is not on the menu"
LIVE_TASK = (
    TASK
    + "\n\nTranscript:\n"
    + TRANSCRIPT
    + "\n\nEmit only XML. Read the order, then one claim that asks counter, then an answer.\n"
    + "The order body is JSON on one line:\n"
    + '<step kind="tool_intent" reversible="true">'
    + '{"name":"read_order","args":{"transcript":"cone with bacon"}}</step>\n'
    + '<step kind="claim">ask counter</step>\n'
)


class OrderDesk:
    """Host desk. The menu check is stored on the call. Placement is refused here."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def execute(self, name: str, args: dict) -> str:
        if name == "place_order":
            result = "not placed"
        elif name == "read_order":
            result = ORDER_RESULT
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


def compose_escalation(first, task: str, tool=None) -> tuple[str, set[str]]:
    """Build the package after the supervisor names counter."""
    if first.escalate_to != "counter":
        return "", set()
    note = next(event.payload for event in first.events if event.type == "floor.escalate")
    calls = [dict(call) for call in note["tool_calls"]]
    if tool is not None and not any(call["name"] == "read_order" for call in calls):
        tool.execute("read_order", {"transcript": TRANSCRIPT})
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


def run_order_crew(monitor, taker_llm, make_counter, desk=None, task: str = TASK) -> OrderCrewResult:
    """Two roles. The counter task receives the host package. The crew does not kick off."""
    desk = desk or OrderDesk()
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
    taker_task = Task(description=TRANSCRIPT, expected_output="Order note.", agent=taker)
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
    composed, written = compose_escalation(first, task, desk)
    result.package = composed
    counter_task.description = composed
    result.counter_ran = True
    result.second = run_session(
        llm=make_counter(composed),
        monitor=monitor,
        tool_policy=_block_place(written),
    )
    return result


def run_live_order(monitor: ScriptedMonitor) -> OrderCrewResult:
    """Run the order taker and, when named, the counter role on the live model."""
    monitor = _OneEscalation(monitor)
    taker = LiveLlm(user_prompt=LIVE_TASK, timeout_s=180.0)
    return run_order_crew(monitor, taker, live_counter)


def _load_dotenv(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    _load_dotenv()
    if not (os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")):
        print("skip live: no LLM_API_KEY")
        return 0
    monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="counter",
        escalate_to="counter",
    )
    result = run_live_order(monitor)
    print("escalate_to", None if result.first is None else result.first.escalate_to)
    print("package", TASK in result.package and "role: counter" in result.package)
    print("order_result", f"result read_order: {ORDER_RESULT}" in result.package)
    print("counter_ran", result.counter_ran)
    print("first_answer", None if result.first is None else result.first.committed_answer)
    print("counter_answer", None if result.second is None else result.second.committed_answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
