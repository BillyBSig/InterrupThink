"""Two LangGraph nodes call run_session; the host forwards retrieved text."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from interrupthink import JsonlLogger, LlmMonitor, SandboxWriteTool, run_session
from src.providers.live import LiveLlm

from config import (
    DEFAULT_SANDBOX,
    RETRIEVE_TICKET_CURRENT,
    RETRIEVE_TICKET_STALE,
    STALE_INSTRUCTIONS,
    STALE_MEMO,
    T4_13_FIXTURES,
)
from tools import FixtureRetrieveTool


class PipeState(TypedDict, total=False):
    blocked: bool
    forwarded: str | None
    session_count: int


@dataclass
class PipeOutcome:
    retrieve_result: Any
    write_result: Any
    retrieve_tool: FixtureRetrieveTool
    write_tool: SandboxWriteTool
    session_count: int
    forwarded: str | None
    sandbox: Path
    session_tools: list[str]
    write_node_visits: int

    @property
    def decision_exists(self) -> bool:
        return (self.sandbox / "decision.txt").is_file()


def stale_mismatch(unit) -> bool:
    text = unit.text.lower()
    if any(p in text for p in ("not in force", "do not treat", "superseded")):
        return False
    return "stale policy is in force" in text or "refunds are banned" in text


def stale_monitor() -> LlmMonitor:
    return LlmMonitor(
        ask=None,
        memo=STALE_MEMO,
        instructions=STALE_INSTRUCTIONS,
        mismatch=stale_mismatch,
        default_missing="stale 2019 policy is not in force; do not write decision.txt",
        default_directive="do not treat stale policy as current; do not write",
    )


def _live_llm(ticket: str):
    llm = LiveLlm(user_prompt=ticket, timeout_s=180.0)
    llm.resume_mode = "rollback"
    return llm


def _write_xml(forwarded: str) -> str:
    payload = json.dumps(
        {"name": "write", "args": {"path": "decision.txt", "content": forwarded}},
        ensure_ascii=False,
    )
    return f"""
<step kind="plan">write the refund decision using retrieved policy</step>
<step kind="premise">retrieved current policy forwarded by host; refunds allowed</step>
<step kind="tool_intent" reversible="false">{payload}</step>
<answer>Wrote decision.txt from retrieved policy.</answer>
"""


def create_pipe_graph(
    *,
    interrupt_stale: bool,
    sandbox: Path | None = None,
    fixtures: Path | None = None,
    logger=None,
    retrieve_llm=None,
    write_llm=None,
    monitor=None,
):
    root = Path(sandbox) if sandbox is not None else DEFAULT_SANDBOX
    leftover = root / "decision.txt"
    if leftover.is_file():
        leftover.unlink()
    policy = Path(fixtures) if fixtures is not None else T4_13_FIXTURES
    retrieve_tool = FixtureRetrieveTool(policy)
    write_tool = SandboxWriteTool(root)
    logger = logger or JsonlLogger()
    if monitor is None:
        monitor = stale_monitor()
    if retrieve_llm is None:
        ticket = RETRIEVE_TICKET_STALE if interrupt_stale else RETRIEVE_TICKET_CURRENT
        retrieve_llm = _live_llm(ticket)
    box: dict = {
        "retrieve_result": None,
        "write_result": None,
        "session_count": 0,
        "session_tools": [],
        "write_node_visits": 0,
        "forwarded": None,
        "retrieve_tool": retrieve_tool,
        "write_tool": write_tool,
        "root": root,
        "write_llm": write_llm,
    }

    def retrieve(state: PipeState) -> PipeState:
        result = run_session(
            llm=retrieve_llm, monitor=monitor, tool=retrieve_tool, logger=logger
        )
        box["retrieve_result"] = result
        box["session_count"] += 1
        box["session_tools"].append("retrieve")
        blocked = bool(result.interrupt_ids)
        forwarded = None
        if not blocked and retrieve_tool.retrieved:
            forwarded = retrieve_tool.retrieved[-1]
        box["forwarded"] = forwarded
        return {
            "blocked": blocked,
            "forwarded": forwarded,
            "session_count": box["session_count"],
        }

    def write(state: PipeState) -> PipeState:
        box["write_node_visits"] += 1
        forwarded = state.get("forwarded") or box.get("forwarded") or ""
        llm = box["write_llm"]
        if llm is None:
            llm = _live_llm(
                "Host forwarded this retrieved policy. Write decision.txt with exactly that text.\n"
                f"Policy:\n{forwarded}\n"
                "Emit ONLY XML with tool_intent write path=decision.txt and that content."
            )
        result = run_session(
            llm=llm,
            monitor=monitor,
            tool=write_tool,
            logger=logger,
        )
        box["write_result"] = result
        box["session_count"] += 1
        box["session_tools"].append("write")
        return {"session_count": box["session_count"]}

    def route(state: PipeState) -> str:
        if state.get("blocked"):
            return END
        return "write"

    graph = StateGraph(PipeState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("write", write)
    graph.add_edge(START, "retrieve")
    graph.add_conditional_edges("retrieve", route, {"write": "write", END: END})
    graph.add_edge("write", END)
    return graph.compile(), box


def run_langgraph_pipe(
    *,
    interrupt_stale: bool,
    sandbox: Path | None = None,
    fixtures: Path | None = None,
    logger=None,
    retrieve_llm=None,
    write_llm=None,
    monitor=None,
) -> PipeOutcome:
    compiled, box = create_pipe_graph(
        interrupt_stale=interrupt_stale,
        sandbox=sandbox,
        fixtures=fixtures,
        logger=logger,
        retrieve_llm=retrieve_llm,
        write_llm=write_llm,
        monitor=monitor,
    )
    compiled.invoke({"blocked": False, "forwarded": None, "session_count": 0})
    return PipeOutcome(
        retrieve_result=box["retrieve_result"],
        write_result=box["write_result"],
        retrieve_tool=box["retrieve_tool"],
        write_tool=box["write_tool"],
        session_count=int(box["session_count"]),
        forwarded=box["forwarded"],
        sandbox=box["root"],
        session_tools=list(box["session_tools"]),
        write_node_visits=int(box["write_node_visits"]),
    )


def analyze(out: PipeOutcome) -> dict:
    r1 = out.retrieve_result
    r2 = out.write_result
    return {
        "session_count": out.session_count,
        "session_tools": list(out.session_tools),
        "interrupt_ids": list(r1.interrupt_ids),
        "retrieve_calls": list(out.retrieve_tool.calls),
        "write_calls": list(out.write_tool.calls),
        "written": list(out.write_tool.written),
        "forwarded": out.forwarded,
        "decision_exists": out.decision_exists,
        "write_node_visits": out.write_node_visits,
        "retrieve_answer": r1.committed_answer,
        "write_answer": None if r2 is None else r2.committed_answer,
    }
