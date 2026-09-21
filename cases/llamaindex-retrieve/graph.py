"""One run_session: LlamaIndex retrieve then sandbox write. QueryEngine is not the think loop."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from interrupthink import JsonlLogger, LlmMonitor, run_session
from src.providers.live import LiveOpenAILlm

from config import (
    CURRENT_TICKET,
    DEFAULT_SANDBOX,
    STALE_INSTRUCTIONS,
    STALE_MEMO,
    STALE_TICKET,
    T4_13_FIXTURES,
)
from tools import RetrieveThenWriteTool, build_policy_retriever, live_embed_model


@dataclass
class SessionOutcome:
    result: Any
    tool: RetrieveThenWriteTool
    sandbox: Path
    retriever_class: str

    @property
    def notice_exists(self) -> bool:
        return (self.sandbox / "notice.txt").is_file()


def stale_mismatch(unit) -> bool:
    text = unit.text.lower()
    if any(p in text for p in ("superseded", "do not post", "not in force")):
        return False
    return "retrieved policy is in force" in text or "refunds are banned" in text


def stale_monitor(*, interrupt: bool) -> LlmMonitor:
    if interrupt:
        return LlmMonitor(
            ask=None,
            memo=STALE_MEMO,
            instructions=STALE_INSTRUCTIONS,
            mismatch=stale_mismatch,
            default_missing="stale retrieve is not in force; do not post a notice",
            default_directive="do not write notice.txt from a stale chunk",
        )
    return LlmMonitor(ask=lambda unit: {"status": "Ok"}, memo=STALE_MEMO)


def _live_llm(ticket: str):
    llm = LiveOpenAILlm(user_prompt=ticket, timeout_s=180.0)
    llm.resume_mode = "rollback"
    return llm


def run_llamaindex_retrieve(
    *,
    interrupt_stale: bool,
    sandbox: Path | None = None,
    fixtures: Path | None = None,
    logger=None,
    llm=None,
    monitor=None,
    embed_model=None,
) -> SessionOutcome:
    fixtures = Path(fixtures) if fixtures is not None else T4_13_FIXTURES
    sandbox = Path(sandbox) if sandbox is not None else DEFAULT_SANDBOX
    leftover = sandbox / "notice.txt"
    if leftover.is_file():
        leftover.unlink()
    retriever = build_policy_retriever(
        interrupt_stale=interrupt_stale,
        fixtures=fixtures,
        embed_model=embed_model if embed_model is not None else live_embed_model(),
    )
    tool = RetrieveThenWriteTool(retriever, sandbox)
    logger = logger or JsonlLogger()
    if llm is None:
        llm = _live_llm(STALE_TICKET if interrupt_stale else CURRENT_TICKET)
    if monitor is None:
        monitor = stale_monitor(interrupt=interrupt_stale)
    result = run_session(llm=llm, monitor=monitor, tool=tool, logger=logger)
    return SessionOutcome(
        result=result,
        tool=tool,
        sandbox=sandbox,
        retriever_class=type(retriever).__name__,
    )


def analyze(out: SessionOutcome) -> dict:
    events = [r.get("event") for r in out.result.log_records]
    return {
        "committed_answer": out.result.committed_answer,
        "interrupt_ids": list(out.result.interrupt_ids),
        "request_count": out.result.request_count,
        "tool_calls": list(out.tool.calls),
        "retrieve_calls": list(out.tool.retrieve.calls),
        "write_calls": list(out.tool.write.calls),
        "written": list(out.tool.write.written),
        "notice_exists": out.notice_exists,
        "retrieved": list(out.tool.retrieve.retrieved),
        "retriever_class": out.retriever_class,
        "event_sequence": events,
    }
