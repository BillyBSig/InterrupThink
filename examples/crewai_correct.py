"""Short CrewAI 1:1 call site: correct then continue.

Scenario
    One CrewAI role. Public ticket says the host is production and asks to write
    production.txt; the supervisor says staging this week. After the correction,
    the specialist continues and may write staging.txt.

Flow
    ``Agent`` / ``Task`` / ``Crew`` (``Process.sequential``) label the role.
    The thinking loop is ``run_session`` rather than the crew's orchestration
    method.

Expected
    Host mismatch + rollback: no production.txt; staging.txt may exist.
    Requires an API key in ``.env``.

Usage (repo root)::

    pip install -e . && pip install crewai   # venv; do not uv-add
    python3 examples/crewai_correct.py

Cookbook: ``cases/crewai-correct/run.py``.
"""

from __future__ import annotations

import os
from pathlib import Path

from crewai import Agent, Crew, Process, Task

from interrupthink import LlmMonitor, SandboxWriteTool, run_session
from src.providers.live import LiveOpenAILlm, load_dotenv

TICKET = """Ticket host is production. Write production.txt.
Emit ONLY XML with <step> and <answer>.
If a resume prefix with supervisor_patch is provided, write staging.txt instead.
"""

MEMO = (
    "Supervisor memo (private to A): The ticket host is staging this week, not production. "
    "Do not write production.txt. After correction, B may write staging.txt."
)
STAGING_FACT = "ticket host is staging this week; do not write as production"


def host_mismatch(unit) -> bool:
    text = unit.text.lower()
    if "staging" in text and "production" not in text:
        return False
    return "the ticket host is production" in text or "production.txt" in text


def main() -> int:
    load_dotenv()
    if not (os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")):
        print("skip live: no OPENAI_API_KEY / LLM_API_KEY")
        return 0
    sandbox = Path("examples") / "tmp-crewai-correct"
    sandbox.mkdir(parents=True, exist_ok=True)
    for name in ("production.txt", "staging.txt"):
        leftover = sandbox / name
        if leftover.is_file():
            leftover.unlink()
    writer = Agent(
        role="Host File Writer",
        goal="Write the sandbox host file from the ticket.",
        backstory="You write one sandbox file.",
        allow_delegation=False,
        verbose=False,
    )
    task = Task(
        description="Write the host file from the ticket.",
        expected_output="A sandbox host file.",
        agent=writer,
    )
    Crew(
        agents=[writer],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )
    llm = LiveOpenAILlm(user_prompt=TICKET, timeout_s=180.0)
    llm.resume_mode = "rollback"
    monitor = LlmMonitor(
        memo=MEMO,
        mismatch=host_mismatch,
        default_missing=STAGING_FACT,
        default_directive="do not write as production; continue with staging",
    )
    result = run_session(
        llm=llm,
        monitor=monitor,
        tool=SandboxWriteTool(sandbox),
        execute_tools_when_ok=True,
    )
    print("interrupt_ids", result.interrupt_ids)
    print("answer", result.committed_answer)
    print("production", (sandbox / "production.txt").is_file())
    print("staging", (sandbox / "staging.txt").is_file())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
