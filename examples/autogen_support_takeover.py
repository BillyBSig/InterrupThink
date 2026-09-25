"""A human receives the support package, and no second agent continues.

Scenario
    A support agent is tracking a parcel. The supervisor names ``human`` before
    an off-task reply is committed. The human sees the package. AutoGen does
    not open another agent to continue that reply.

Expected
    The off-task reply is not committed and is not sent.
    The support agent does not resume. Only the support agent is constructed.

Usage (repo root)::

    pip install -e . && pip install autogen   # venv; do not uv-add
    python3 examples/autogen_support_takeover.py

Cookbook: ``cases/autogen-support/run.py``.
"""

from __future__ import annotations

import os
from pathlib import Path

from autogen import ConversableAgent

from interrupthink import LiveLlm, ScriptedMonitor, Takeover, Verdict, run_session

TASK = "Track the customer's parcel and stay on that support task."
HOLD_RESULT = "not sent"
LIVE_TASK = (
    TASK
    + "\n\nEmit only XML. Hold the reply, then one claim that the supervisor should take this.\n"
    + "Do not write a poem. Stay on the parcel until the supervisor is named.\n"
    + "The reply body is JSON on one line:\n"
    + 'tool_intent reversible: ' + '{"name":"hold_reply","args":{"topic":"parcel"}}\n'
    + 'claim: the supervisor should take this\n'
)


class SupportDesk:
    """Host desk. An off-task reply is held and recorded as not sent."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def execute(self, name: str, args: dict) -> str:
        result = HOLD_RESULT if name == "hold_reply" else "ok"
        self.calls.append({"name": name, "args": dict(args), "result": result})
        return result


class SupportResult:
    def __init__(self) -> None:
        self.first = None
        self.package = ""
        self.agents: list[str] = []


def receiver_input(task: str, note: dict, role: str, reason: str) -> str:
    """Compose the human's package from the imported object."""
    noted = dict(note)
    noted["takeover_to"] = role
    noted["reason"] = reason
    return Takeover.from_note(task, noted).text()


def compose_takeover(first, task: str, tool=None) -> str:
    """Build the package after the supervisor names human. Does not open a session."""
    if first.takeover_to != "human":
        return ""
    note = next(event.payload for event in first.events if event.type == "floor.takeover")
    calls = [dict(call) for call in note["tool_calls"]]
    if tool is not None and not any(call["name"] == "hold_reply" for call in calls):
        tool.execute("hold_reply", {"topic": "parcel"})
        calls.append(dict(tool.calls[-1]))
    note = {**note, "tool_calls": calls}
    return receiver_input(task, note, str(note["takeover_to"]), str(note.get("reason") or ""))


class _OneTakeover:
    """Open the human owner once. A later claim stays with that owner."""

    def __init__(self, inner: ScriptedMonitor) -> None:
        self.inner = inner
        self.opened = False

    def verdict(self, unit):
        if unit.kind == "claim" and "supervisor" in unit.text.casefold() and "\n" not in unit.text:
            if self.opened:
                return Verdict(unit_id=unit.id, status="Ok", reason="takeover already opened")
            self.opened = True
            return Verdict(
                unit_id=unit.id,
                status="Ok",
                reason="named owner",
                takeover_to="human",
            )
        return self.inner.verdict(unit)

    def __getattr__(self, name):
        return getattr(self.inner, name)


def run_support_chat(monitor, agent_llm, desk=None, task: str = TASK) -> SupportResult:
    """One support agent. Naming human returns the package and starts nobody else."""
    desk = desk or SupportDesk()
    result = SupportResult()
    support = ConversableAgent(
        name="support",
        system_message=TASK,
        llm_config=False,
        human_input_mode="NEVER",
        code_execution_config=False,
    )
    result.agents.append(support.name)
    first = run_session(llm=agent_llm, monitor=monitor, tool=desk)
    result.first = first
    if first.takeover_to != "human":
        return result
    result.package = compose_takeover(first, task, desk)
    return result


def run_live_support(monitor: ScriptedMonitor) -> SupportResult:
    """Run the support agent on the live model and stop at the human package."""
    monitor = _OneTakeover(monitor)
    agent = LiveLlm(user_prompt=LIVE_TASK, timeout_s=180.0)
    return run_support_chat(monitor, agent)


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
        trigger_contains="supervisor",
        takeover_to="human",
    )
    result = run_live_support(monitor)
    print("takeover_to", None if result.first is None else result.first.takeover_to)
    print("package", TASK in result.package and "role: human" in result.package)
    print("held", f"result hold_reply: {HOLD_RESULT}" in result.package)
    print("agents", result.agents)
    print("first_answer", None if result.first is None else result.first.committed_answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
