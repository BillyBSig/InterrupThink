"""One support agent. Naming human returns the package and starts nobody else."""

from __future__ import annotations

from autogen import ConversableAgent

from interrupthink import LiveLlm, ScriptedMonitor, Takeover, Verdict, run_session


class SupportDesk:
    """Host desk. An off-task reply is held and recorded as not sent."""

    def __init__(self, held_result: str) -> None:
        self.calls: list[dict] = []
        self.held_result = held_result

    def execute(self, name: str, args: dict) -> str:
        result = self.held_result if name == "hold_reply" else "ok"
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


def live_task(task: str) -> str:
    return (
        task
        + "\n\nEmit only XML. Hold the reply, then one claim that the supervisor should take this.\n"
        + "Do not write a poem. Stay on the parcel until the supervisor is named.\n"
        + "The reply body is JSON on one line:\n"
        + 'tool_intent reversible: ' + '{"name":"hold_reply","args":{"topic":"parcel"}}\n'
        + 'claim: the supervisor should take this\n'
    )


def run_support_chat(monitor, agent_llm, desk, task: str) -> SupportResult:
    """One support agent. Naming human returns the package and starts nobody else."""
    result = SupportResult()
    support = ConversableAgent(
        name="support",
        system_message=task,
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


def run_live_support(monitor: ScriptedMonitor, desk, task: str) -> SupportResult:
    """Run the support agent on the live model and stop at the human package."""
    monitor = _OneTakeover(monitor)
    agent = LiveLlm(user_prompt=live_task(task), timeout_s=180.0)
    return run_support_chat(monitor, agent, desk, task)
