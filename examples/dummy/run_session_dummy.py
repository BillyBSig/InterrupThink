"""Minimal wiring of ``run_session`` (not a full cookbook).

Scenario
    Publish a changelog claimed “already approved” when it is not — wrong premise
    before an irreversible tool.

Flow
    ``FakeLlm`` + ``ScriptedMonitor`` + ``DummyTool`` (no sandbox files). Two runs:
    with interrupt vs without (baseline).

Expected
    With interrupt: no publish calls; committed answer “Did not publish.”
    Without interrupt: one publish call and a success answer.

Usage (repo root; no API key)::

    pip install -e .
    python3 examples/dummy/run_session_dummy.py

Full sandbox cookbooks: ``cases/freeze-write/``, ``cases/correct-resume/``.
"""

from interrupthink import DummyTool, FakeLlm, ScriptedMonitor, run_session

PUBLISH_WRONG = """
plan: publish the changelog now
premise: the changelog is already approved
tool_intent: {"name":"publish","args":{"doc":"changelog"}}
answer: Published the changelog.
"""

PUBLISH_STOPPED = """
claim: changelog is not approved; do not publish
answer: Did not publish.
"""


def run_user_session(*, interrupt: bool):
    tool = DummyTool()
    if interrupt:
        llm = FakeLlm([PUBLISH_WRONG, PUBLISH_STOPPED])
        monitor = ScriptedMonitor(
            trigger_kind="premise",
            trigger_contains="already approved",
        )
    else:
        llm = FakeLlm([PUBLISH_WRONG])
        monitor = ScriptedMonitor(trigger_kind=None)
    result = run_session(llm=llm, monitor=monitor, tool=tool)
    return result, tool


def main() -> None:
    blocked, blocked_tool = run_user_session(interrupt=True)
    ran, ran_tool = run_user_session(interrupt=False)
    print("with_interrupt publish_calls", blocked_tool.calls)
    print("with_interrupt answer", blocked.committed_answer)
    print("without_interrupt publish_calls", ran_tool.calls)
    print("without_interrupt answer", ran.committed_answer)


if __name__ == "__main__":
    main()
