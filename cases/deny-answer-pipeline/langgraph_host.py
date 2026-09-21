"""Optional LangGraph host for the deny-answer workflow."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from interrupthink import JsonlLogger, SandboxWriteTool


class PipeState(TypedDict):
    blocked: bool


def run_deny_answer_langgraph(
    *,
    interrupt: bool,
    sandbox: Path,
    native,
    logger=None,
    monitor=None,
    answer_llm=None,
    send_llm=None,
):
    """Two nodes wrapping the same specialists as the native host."""
    sandbox = Path(sandbox)
    native._clear(sandbox)
    logger = logger or JsonlLogger()
    if monitor is None:
        monitor = native.policy_monitor(interrupt=interrupt)
    box: dict = {}

    def answer_node(state: PipeState) -> PipeState:
        result, tool = native.run_answer_specialist(
            interrupt=interrupt,
            sandbox=sandbox,
            logger=logger,
            monitor=monitor,
            llm=answer_llm,
        )
        box["answer_result"] = result
        box["answer_tool"] = tool
        return {"blocked": bool(result.interrupt_ids)}

    def send_node(state: PipeState) -> PipeState:
        forwarded = box["answer_result"].committed_answer
        send_tool = SandboxWriteTool(sandbox)
        result, send_tool = native.run_send_specialist(
            forwarded=forwarded or "",
            sandbox=sandbox,
            logger=logger,
            monitor=monitor,
            tool=send_tool,
            llm=send_llm,
        )
        box["send_result"] = result
        box["send_tool"] = send_tool
        box["forwarded"] = forwarded
        return state

    def route(state: PipeState) -> str:
        return "send" if not state.get("blocked") else END

    graph = StateGraph(PipeState)
    graph.add_node("answer", answer_node)
    graph.add_node("send", send_node)
    graph.add_edge(START, "answer")
    graph.add_conditional_edges("answer", route, {"send": "send", END: END})
    graph.add_edge("send", END)
    graph.compile().invoke({"blocked": False})

    answer_result = box["answer_result"]
    send_result = box.get("send_result")
    send_tool = box.get("send_tool") or SandboxWriteTool(sandbox)
    session_tools = ["answer"] if send_result is None else ["answer", "send"]
    return native.PipelineOutcome(
        answer_result=answer_result,
        send_result=send_result,
        answer_tool=box["answer_tool"],
        send_tool=send_tool,
        session_count=1 if send_result is None else 2,
        forwarded=box.get("forwarded"),
        sandbox=sandbox,
        session_tools=session_tools,
    )
