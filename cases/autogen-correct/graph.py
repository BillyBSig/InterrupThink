"""One AutoGen agent. Think loop = run_session. Not initiate_chat, not two specialists."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from autogen import ConversableAgent

from interrupthink import JsonlLogger, LlmMonitor, SandboxWriteTool, run_session
from src.providers.live import LiveLlm

from config import (
    DEFAULT_SANDBOX,
    DEFAULT_TICKET,
    HOST_INSTRUCTIONS,
    HOST_MEMO,
    STAGING_FACT,
    SYSTEM_INSTRUCTIONS,
    WRONG_HOST,
)


@dataclass
class CorrectOutcome:
    result: Any
    tool: SandboxWriteTool
    sandbox: Path
    agent: Any

    @property
    def production_exists(self) -> bool:
        return (self.sandbox / "production.txt").is_file()

    @property
    def staging_exists(self) -> bool:
        return (self.sandbox / "staging.txt").is_file()


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


def format_ticket(ticket: str | None = None) -> str:
    return f"{SYSTEM_INSTRUCTIONS}\n\n{ticket or DEFAULT_TICKET}"


def _clear(sandbox: Path) -> None:
    sandbox.mkdir(parents=True, exist_ok=True)
    for name in ("production.txt", "staging.txt"):
        leftover = sandbox / name
        if leftover.is_file():
            leftover.unlink()


def _role_agent() -> ConversableAgent:
    return ConversableAgent(
        name="host_file_writer",
        system_message=(
            "Write the sandbox host file from the ticket, after any supervisor correction. "
            "Do not retrieve. Do not chat with another agent."
        ),
        llm_config=False,
        human_input_mode="NEVER",
        code_execution_config=False,
    )


def run_autogen_correct(
    *,
    interrupt: bool = True,
    sandbox: Path | None = None,
    ticket: str | None = None,
    llm=None,
    monitor=None,
    logger=None,
) -> CorrectOutcome:
    root = Path(sandbox) if sandbox is not None else DEFAULT_SANDBOX
    _clear(root)
    tool = SandboxWriteTool(root)
    logger = logger or JsonlLogger()
    if llm is None:
        llm = LiveLlm(user_prompt=format_ticket(ticket), timeout_s=180.0)
        llm.resume_mode = "rollback"
    if monitor is None:
        monitor = host_monitor(interrupt=interrupt)
    agent = _role_agent()
    result = run_session(
        llm=llm,
        monitor=monitor,
        tool=tool,
        logger=logger,
        execute_tools_when_ok=True,
    )
    return CorrectOutcome(
        result=result,
        tool=tool,
        sandbox=root,
        agent=agent,
    )


def analyze(out: CorrectOutcome) -> dict:
    resumes = [r for r in out.result.log_records if r.get("event") == "floor.resume"]
    resume_prefix = resumes[0].get("prefix") if resumes else ""
    return {
        "committed_answer": out.result.committed_answer,
        "interrupt_ids": list(out.result.interrupt_ids),
        "request_count": out.result.request_count,
        "tool_calls": list(out.tool.calls),
        "written": list(out.tool.written),
        "production_exists": out.production_exists,
        "staging_exists": out.staging_exists,
        "event_sequence": [r.get("event") for r in out.result.log_records],
        "resume_modes": [r.get("mode") for r in resumes],
        "resume_prefix": resume_prefix,
        "binding": resumes[0].get("binding") if resumes else None,
        "human_input_mode": out.agent.human_input_mode,
        "agent_name": out.agent.name,
    }
