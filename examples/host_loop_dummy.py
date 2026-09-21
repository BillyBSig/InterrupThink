"""Host that only gates at ``tool.execute`` (HITL-at-tools analog).

Scenario
    Same freeze + push story as ``freeze_push_dummy.py``, but the host always approves
    tool execution — too late if a wrong premise was not cut at the ThoughtUnit.

Flow
    ``run_session`` plus a host wrapper that approves every ``tool.execute``. Compare
    ThoughtUnit interrupt vs no interrupt.

Expected
    With ThoughtUnit interrupt: host never approves push (tool never runs).
    Without interrupt: host approves and push is recorded — why interrupt at the step,
    not only at the tool boundary.

Usage (repo root; no API key)::

    pip install -e .
    python3 examples/host_loop_dummy.py
"""

from interrupthink import DummyTool, FakeLlm, ScriptedMonitor, run_session

PUSH_WRONG = """
<step kind="plan">push the hotfix to origin main</step>
<step kind="premise">the code freeze is over; main is clear to receive the fix</step>
<step kind="tool_intent" reversible="false">{"name":"push","args":{"remote":"origin","branch":"main"}}</step>
<answer>Pushed hotfix to origin/main.</answer>
"""

PUSH_STOPPED = """
<step kind="claim">code freeze is still in force; do not push</step>
<answer>Did not push. Freeze still holds.</answer>
"""


class ToolBoundaryHost:
    """Stands in for interrupt_before=['tools']: sees calls only at execute."""

    def __init__(self) -> None:
        self.approvals: list[dict] = []

    def approve(self, name: str, args: dict) -> bool:
        self.approvals.append({"name": name, "args": args})
        return True


class HostGatedTool:
    """Dummy tool behind the host gate. Not a new public helper."""

    def __init__(self, inner: DummyTool, host: ToolBoundaryHost) -> None:
        self._inner = inner
        self._host = host

    @property
    def calls(self) -> list[dict]:
        return self._inner.calls

    def execute(self, name: str, args: dict) -> str:
        if not self._host.approve(name, args):
            return "denied"
        return self._inner.execute(name, args)


def run_host_loop(*, interrupt: bool):
    tool = DummyTool()
    host = ToolBoundaryHost()
    gated = HostGatedTool(tool, host)
    if interrupt:
        llm = FakeLlm([PUSH_WRONG, PUSH_STOPPED])
        monitor = ScriptedMonitor(
            trigger_kind="premise",
            trigger_contains="code freeze is over",
        )
    else:
        llm = FakeLlm([PUSH_WRONG])
        monitor = ScriptedMonitor(trigger_kind=None)
    result = run_session(llm=llm, monitor=monitor, tool=gated)
    return result, tool, host


def main() -> None:
    blocked, blocked_tool, blocked_host = run_host_loop(interrupt=True)
    ran, ran_tool, ran_host = run_host_loop(interrupt=False)
    print("with_interrupt host_approvals", blocked_host.approvals)
    print("with_interrupt push_calls", blocked_tool.calls)
    print("with_interrupt answer", blocked.committed_answer)
    print("without_interrupt host_approvals", ran_host.approvals)
    print("without_interrupt push_calls", ran_tool.calls)
    print("without_interrupt answer", ran.committed_answer)


if __name__ == "__main__":
    main()
