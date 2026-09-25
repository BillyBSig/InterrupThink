"""A policy specialist receives the fare package, and the front agent stops.

Scenario
    A passenger asks for a retroactive bereavement fare. The host reads the
    policy and records that the fare is not offered. The supervisor names
    ``policy`` before that promise is committed. The specialist sees the same
    task, the role, the reason, the kept steps, the policy result, and the
    tools that must not be repeated.

Expected
    The front agent does not commit the refund promise.
    The policy specialist answers from the policy result and does not send it again.

Usage (repo root)::

    pip install -e .
    python3 examples/fare_escalation.py
"""

from __future__ import annotations

import os
from pathlib import Path

from interrupthink import Escalation, LiveLlm, ScriptedMonitor, Verdict, run_session

TASK = (
    "A passenger asks for a retroactive bereavement fare refund. "
    "Answer only what the policy allows."
)
POLICY_RESULT = "retroactive bereavement fare is not offered"
PROMISE_RESULT = "sent"
LIVE_TASK = (
    TASK
    + "\n\nEmit only XML. Read the policy, then one claim that asks policy, then an answer.\n"
    + "The lookup body is JSON on one line:\n"
    + 'tool_intent reversible: ' + '{"name":"read_policy","args":{"topic":"bereavement fare"}}\n'
    + 'claim: ask policy\n'
)


class FareDesk:
    """Host desk. Policy text and any promise are stored on the call."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def execute(self, name: str, args: dict) -> str:
        if name == "read_policy":
            result = POLICY_RESULT
        elif name == "promise_refund":
            result = PROMISE_RESULT
        else:
            result = "ok"
        self.calls.append({"name": name, "args": dict(args), "result": result})
        return result


def receiver_input(task: str, note: dict, role: str, reason: str) -> str:
    """Compose the specialist's input from the imported package."""
    noted = dict(note)
    noted["escalate_to"] = role
    noted["reason"] = reason
    return Escalation.from_note(task, noted).text()


class _OneEscalation:
    """Open policy once. A later claim that mentions policy stays put."""

    def __init__(self, inner: ScriptedMonitor) -> None:
        self.inner = inner
        self.opened = False

    def verdict(self, unit):
        if unit.kind == "claim" and "policy" in unit.text.casefold() and "\n" not in unit.text:
            if self.opened:
                return Verdict(unit_id=unit.id, status="Ok", reason="escalation already opened")
            self.opened = True
            return Verdict(
                unit_id=unit.id,
                status="Ok",
                reason="named specialist",
                escalate_to="policy",
            )
        return self.inner.verdict(unit)

    def __getattr__(self, name):
        return getattr(self.inner, name)


def live_specialist(composed: str) -> LiveLlm:
    """The specialist sees the package, including the policy result."""
    return LiveLlm(
        user_prompt=(
            composed
            + "\n\nEmit one claim and one answer. Do not emit tool_intent. "
            + "Use the policy result in the package. "
            + "If the fare is not offered, say the retroactive bereavement fare is not offered."
        ),
        timeout_s=180.0,
    )


def handoff_escalation(first, task: str, monitor, make_specialist, tool=None):
    """Give the named specialist the package. The front agent does not resume."""
    if first.escalate_to != "policy":
        return first, None, ""
    note = next(event.payload for event in first.events if event.type == "floor.escalate")
    calls = [dict(call) for call in note["tool_calls"]]
    if tool is not None and not any(call["name"] == "read_policy" for call in calls):
        tool.execute("read_policy", {"topic": "bereavement fare"})
        calls.append(tool.calls[-1])
    note = {**note, "tool_calls": calls}
    composed = receiver_input(task, note, str(note["escalate_to"]), str(note.get("reason") or ""))
    specialist = make_specialist(composed)
    written = {str(call["name"]) for call in note["tool_calls"]}
    second = run_session(
        llm=specialist,
        monitor=monitor,
        tool_policy=lambda name, args: name not in written,
    )
    return first, second, composed


def run_fare_escalation(monitor: ScriptedMonitor):
    """Run the front agent and the policy specialist on the live model."""
    monitor = _OneEscalation(monitor)
    desk = FareDesk()
    front = LiveLlm(user_prompt=LIVE_TASK, timeout_s=180.0)
    first = run_session(llm=front, monitor=monitor, tool=desk)
    return handoff_escalation(first, LIVE_TASK, monitor, live_specialist, desk)


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
        trigger_contains="policy",
        escalate_to="policy",
    )
    first, second, received = run_fare_escalation(monitor)
    print("escalate_to", first.escalate_to)
    print("package", TASK in received and "role: policy" in received)
    print("policy_result", f"result read_policy: {POLICY_RESULT}" in received)
    print("first_answer", first.committed_answer)
    print("specialist_answer", None if second is None else second.committed_answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
