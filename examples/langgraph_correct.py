"""Short LangGraph 1:1 apply: fill the agent node, keep ToolNode, then continue.

Scenario
    Public ticket says the host is production and asks to write production.txt;
    supervisor memo says staging this week. After the correction, the specialist
    continues and ToolNode
    may write staging.txt (same story as the correct-resume case).

Flow
    ``StateGraph``: START → agent (``run_session``) → tools (``ToolNode``) or END.
    ``LiveLlm`` + ``LlmMonitor``. Route to ToolNode on a kept tool_intent even
    if the session was interrupted. Do not decorate ToolNode.

Expected
    Host mismatch + rollback: no production.txt; staging.txt may exist.
    Requires an API key in ``.env``.

Usage (repo root)::

    pip install -e . && pip install langgraph langchain   # venv; do not uv-add
    python3 examples/langgraph_correct.py

Cookbook: ``cases/langgraph-correct/run.py``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import StructuredTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from interrupthink import LlmMonitor, SandboxWriteTool, run_session
from src.providers.live import LiveLlm, load_dotenv

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


class GraphState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    answer: str | None


def _pending_tool(result) -> dict | None:
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


def main() -> int:
    load_dotenv()
    if not (os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")):
        print("skip live: no OPENAI_API_KEY / LLM_API_KEY")
        return 0
    sandbox = Path("examples") / "tmp-langgraph-correct"
    sandbox.mkdir(parents=True, exist_ok=True)
    for name in ("production.txt", "staging.txt"):
        leftover = sandbox / name
        if leftover.is_file():
            leftover.unlink()
    inner = SandboxWriteTool(sandbox)
    write_tool = StructuredTool.from_function(
        func=lambda path, content: str(inner.execute("write", {"path": path, "content": content})),
        name="write",
        description="Write a file under the sandbox.",
    )
    llm = LiveLlm(user_prompt=TICKET, timeout_s=180.0)
    llm.resume_mode = "rollback"
    monitor = LlmMonitor(
        memo=MEMO,
        mismatch=host_mismatch,
        default_missing=STAGING_FACT,
        default_directive="do not write as production; continue with staging",
    )

    def agent(state: GraphState) -> GraphState:
        result = run_session(llm=llm, monitor=monitor, logger=None, execute_tools_when_ok=False)
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
        return {
            "messages": [AIMessage(content=result.committed_answer or "", tool_calls=tool_calls)],
            "answer": result.committed_answer,
        }

    def route(state: GraphState) -> str:
        last = (state.get("messages") or [None])[-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return END

    graph = StateGraph(GraphState)
    graph.add_node("agent", agent)
    graph.add_node("tools", ToolNode([write_tool]))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", route, {"tools": "tools", END: END})
    graph.add_edge("tools", END)
    out = graph.compile().invoke({"messages": [], "answer": None})
    print("answer", out.get("answer"))
    print("production", (sandbox / "production.txt").is_file())
    print("staging", (sandbox / "staging.txt").is_file())
    print("sandbox_writes", inner.calls)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
