"""One hook: fill the agent node with run_session. Keep ToolNode theirs.

After a cut, the session may resume and emit a corrected tool_intent. Route that
intent to ToolNode. Do not skip tools merely because interrupt_ids is non-empty.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

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


class CorrectState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    interrupted: bool
    answer: str | None


@dataclass
class CorrectOutcome:
    result: Any
    tool: Any
    sandbox: Path
    tool_node_visits: int
    lc_tool: WriteHostTool

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
    body = ticket or DEFAULT_TICKET
    return f"{SYSTEM_INSTRUCTIONS}\n\n{body}"


def _clear(sandbox: Path) -> None:
    sandbox.mkdir(parents=True, exist_ok=True)
    for name in ("production.txt", "staging.txt"):
        leftover = sandbox / name
        if leftover.is_file():
            leftover.unlink()


def _pending_tool(result) -> dict | None:
    """Last kept tool_intent (dropped production intents must not reach ToolNode)."""
    dropped = set(result.dropped_ids or [])
    pending = None
    for rec in result.log_records:
        if rec.get("event") != "thought.unit" or rec.get("kind") != "tool_intent":
            continue
        if rec.get("unit_id") in dropped:
            continue
        try:
            pending = json.loads(rec.get("text") or "")
        except json.JSONDecodeError:
            pending = None
    return pending


def make_agent_node(*, llm, monitor, logger, box: dict):
    """The one written hook: think loop is run_session, not ToolNode."""

    def agent(state: CorrectState) -> CorrectState:
        result = run_session(
            llm=llm,
            monitor=monitor,
            logger=logger,
            execute_tools_when_ok=False,
        )
        box["result"] = result
        pending = _pending_tool(result)
        tool_calls = []
        if pending and pending.get("name"):
            tool_calls.append(
                {
                    "name": str(pending["name"]),
                    "args": dict(pending.get("args") or {}),
                    "id": "call_write",
                    "type": "tool_call",
                }
            )
        message = AIMessage(content=result.committed_answer or "", tool_calls=tool_calls)
        return {
            "messages": [message],
            "interrupted": bool(result.interrupt_ids),
            "answer": result.committed_answer,
        }

    return agent


def _route(state: CorrectState) -> str:
    messages = state.get("messages") or []
    last = messages[-1] if messages else None
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


def create_correct_graph(
    *,
    interrupt: bool = True,
    sandbox: Path | None = None,
    ticket: str | None = None,
    llm=None,
    monitor=None,
    logger=None,
):
    """Practitioner graph: their ToolNode, our agent node."""
    root = Path(sandbox) if sandbox is not None else DEFAULT_SANDBOX
    _clear(root)
    inner, lc_tool = build_write_tool(root)
    logger = logger or JsonlLogger()
    if llm is None:
        llm = LiveOpenAILlm(user_prompt=format_ticket(ticket), timeout_s=180.0)
        llm.resume_mode = "rollback"
    if monitor is None:
        monitor = host_monitor(interrupt=interrupt)
    visits = {"n": 0}
    official = ToolNode([lc_tool])

    def tools(state: CorrectState) -> dict:
        visits["n"] += 1
        return official.invoke(state)

    box: dict = {
        "inner": inner,
        "lc_tool": lc_tool,
        "visits": visits,
        "root": root,
        "logger": logger,
        "result": None,
    }

    graph = StateGraph(CorrectState)
    graph.add_node("agent", make_agent_node(llm=llm, monitor=monitor, logger=logger, box=box))
    graph.add_node("tools", tools)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", _route, {"tools": "tools", END: END})
    graph.add_edge("tools", END)
    compiled = graph.compile()
    return compiled, box


def run_correct(
    *,
    interrupt: bool = True,
    sandbox: Path | None = None,
    ticket: str | None = None,
    llm=None,
    monitor=None,
    logger=None,
) -> CorrectOutcome:
    compiled, box = create_correct_graph(
        interrupt=interrupt,
        sandbox=sandbox,
        ticket=ticket,
        llm=llm,
        monitor=monitor,
        logger=logger,
    )
    compiled.invoke({"messages": [], "interrupted": False, "answer": None})
    result = box["result"]
    return CorrectOutcome(
        result=result,
        tool=box["inner"],
        sandbox=box["root"],
        tool_node_visits=int(box["visits"]["n"]),
        lc_tool=box["lc_tool"],
    )


def analyze(out: CorrectOutcome) -> dict:
    resumes = [r for r in out.result.log_records if r.get("event") == "floor.resume"]
    resume_prefix = resumes[0].get("prefix") if resumes else ""
    return {
        "committed_answer": out.result.committed_answer,
        "interrupt_ids": list(out.result.interrupt_ids),
        "request_count": out.result.request_count,
        "tool_node_visits": out.tool_node_visits,
        "tool_calls": list(out.tool.calls),
        "written": list(out.tool.written),
        "production_exists": out.production_exists,
        "staging_exists": out.staging_exists,
        "lc_tool_name": out.lc_tool.name,
        "event_sequence": [r.get("event") for r in out.result.log_records],
        "resume_modes": [r.get("mode") for r in resumes],
        "resume_prefix": resume_prefix,
        "binding": resumes[0].get("binding") if resumes else None,
    }
