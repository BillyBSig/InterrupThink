"""Factory and wrapper around run_session with a live language model."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda

from interrupthink import JsonlLogger, LlmMonitor, run_session
from src.providers.live import LiveOpenAILlm

from config import (
    DEFAULT_SANDBOX,
    DEFAULT_TICKET,
    HOST_INSTRUCTIONS,
    HOST_MEMO,
    STAGING_FACT,
    SYSTEM_INSTRUCTIONS,
    WRONG_HOST,
)
from tools import WriteHostTool, build_write_tool

TICKET_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "{instructions}"),
        ("human", "{ticket}"),
    ]
)


def format_ticket(ticket: str | None = None) -> str:
    return TICKET_PROMPT.format(
        instructions=SYSTEM_INSTRUCTIONS,
        ticket=ticket or DEFAULT_TICKET,
    )


def host_mismatch(unit) -> bool:
    text = unit.text.lower()
    if "staging" in text and "production" not in text:
        return False
    return WRONG_HOST in text or "production.txt" in text


def host_monitor(*, interrupt: bool) -> LlmMonitor:
    if interrupt:
        return LlmMonitor(
            ask=None,
            memo=HOST_MEMO,
            instructions=HOST_INSTRUCTIONS,
            mismatch=host_mismatch,
            default_missing=STAGING_FACT,
            default_directive="do not write as production; continue with staging",
        )
    return LlmMonitor(ask=lambda unit: {"status": "Ok"}, memo=HOST_MEMO)


def _clear(sandbox: Path) -> None:
    sandbox.mkdir(parents=True, exist_ok=True)
    for name in ("production.txt", "staging.txt"):
        leftover = sandbox / name
        if leftover.is_file():
            leftover.unlink()


@dataclass
class SpecialistOutcome:
    result: Any
    tool: Any
    specialist: Specialist


class Specialist:
    """Thin wrapper. User calls .run() or .as_runnable().invoke(ticket)."""

    def __init__(
        self,
        *,
        llm,
        monitor,
        tool,
        lc_tool: WriteHostTool,
        logger=None,
    ) -> None:
        self.llm = llm
        self.monitor = monitor
        self.tool = tool
        self.tools = [lc_tool]
        self.logger = logger or JsonlLogger()

    def run(self, ticket: str | None = None) -> SpecialistOutcome:
        if ticket is not None and hasattr(self.llm, "user_prompt"):
            self.llm.user_prompt = format_ticket(ticket)
        result = run_session(
            llm=self.llm,
            monitor=self.monitor,
            tool=self.tool,
            logger=self.logger,
            execute_tools_when_ok=True,
        )
        return SpecialistOutcome(result=result, tool=self.tool, specialist=self)

    def as_runnable(self) -> Runnable:
        def _invoke(ticket: str) -> dict:
            return analyze(self.run(ticket))

        return RunnableLambda(_invoke)


def create_specialist(
    *,
    interrupt: bool = True,
    sandbox: Path | None = None,
    ticket: str | None = None,
    llm=None,
    monitor=None,
    logger=None,
) -> Specialist:
    root = Path(sandbox) if sandbox is not None else DEFAULT_SANDBOX
    _clear(root)
    inner, lc_tool = build_write_tool(root)
    if llm is None:
        llm = LiveOpenAILlm(user_prompt=format_ticket(ticket), timeout_s=180.0)
        llm.resume_mode = "rollback"
    if monitor is None:
        monitor = host_monitor(interrupt=interrupt)
    return Specialist(
        llm=llm,
        monitor=monitor,
        tool=inner,
        lc_tool=lc_tool,
        logger=logger,
    )


def analyze(outcome: SpecialistOutcome) -> dict:
    result = outcome.result
    tool = outcome.tool
    resumes = [r for r in result.log_records if r.get("event") == "floor.resume"]
    resume_prefix = resumes[0].get("prefix") if resumes else ""
    sandbox = tool.root
    return {
        "committed_answer": result.committed_answer,
        "interrupt_ids": list(result.interrupt_ids),
        "dropped_ids": list(result.dropped_ids),
        "request_count": result.request_count,
        "tool_calls": list(tool.calls),
        "written": list(tool.written),
        "production_exists": (sandbox / "production.txt").is_file(),
        "staging_exists": (sandbox / "staging.txt").is_file(),
        "event_sequence": [r.get("event") for r in result.log_records],
        "resume_modes": [r.get("mode") for r in resumes],
        "resume_prefix": resume_prefix,
        "binding": resumes[0].get("binding") if resumes else None,
        "lc_tool_name": outcome.specialist.tools[0].name,
    }
