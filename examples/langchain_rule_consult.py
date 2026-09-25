"""The same LangChain chat continues after a rule check.

Scenario
    A shop owner asks whether they may skip a posted city rule. The host
    reads the rule. The supervisor names ``checker`` before that advice is
    committed. The checker sees the package. The patch comes back to this
    same chat.

Expected
    The skipped-rule advice is not committed.
    The same history and the same assistant continue from the checker's answer.

Usage (repo root)::

    pip install -e . && pip install langchain-core   # venv; do not uv-add
    python3 examples/langchain_rule_consult.py

Cookbook: ``cases/langchain-rule/run.py``.
"""

from __future__ import annotations

import os
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from interrupthink import Consult, LiveLlm, Patch, ScriptedMonitor, Verdict, run_session

TASK = (
    "A shop owner asks whether they may skip a posted city rule. "
    "Answer only what the rule check allows."
)
QUESTION = "May I skip the posted city rule?"
RULE_RESULT = "the posted city rule must be followed"
LIVE_QUESTION = (
    QUESTION
    + "\n\nEmit only XML. Read the rule, then one claim that asks the checker, then an answer.\n"
    + "The rule body is JSON on one line:\n"
    + 'tool_intent reversible: ' + '{"name":"read_rule","args":{"topic":"posted city rule"}}\n'
    + 'claim: ask the checker\n'
)
TURN = ChatPromptTemplate.from_messages(
    [
        ("system", "You are the shop assistant. Emit only XML. Stay with this chat."),
        MessagesPlaceholder("history", optional=True),
        ("human", "{question}"),
    ]
)


class RuleDesk:
    """Host desk. The rule text is stored on the call."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def execute(self, name: str, args: dict) -> str:
        result = RULE_RESULT if name == "read_rule" else "ok"
        self.calls.append({"name": name, "args": dict(args), "result": result})
        return result


class ShopChatResult:
    def __init__(self) -> None:
        self.first = None
        self.consult = None
        self.resumed = None
        self.package = ""
        self.history: list = []


def receiver_input(task: str, note: dict, role: str, reason: str) -> str:
    """Compose the checker's input from the imported package."""
    noted = dict(note)
    noted["consult_to"] = role
    noted["reason"] = reason
    return Consult.from_note(task, noted).text()


def compose_consult(first, task: str, tool=None) -> tuple[str, set[str]]:
    """Build the package after the supervisor names the checker."""
    if first.consult_to != "checker":
        return "", set()
    note = next(event.payload for event in first.events if event.type == "floor.consult")
    calls = [dict(call) for call in note["tool_calls"]]
    if tool is not None and not any(call["name"] == "read_rule" for call in calls):
        tool.execute("read_rule", {"topic": "posted city rule"})
        calls.append(dict(tool.calls[-1]))
    note = {**note, "tool_calls": calls}
    composed = receiver_input(task, note, str(note["consult_to"]), str(note.get("reason") or ""))
    return composed, {str(call["name"]) for call in calls}


def remember(history: list, question: str, answer: str) -> None:
    """Keep the turn on this chat. The caller passes the same list back."""
    history.append(HumanMessage(content=question))
    history.append(AIMessage(content=answer))


class _OneConsult:
    """Open the checker once. A later claim that mentions the checker stays put."""

    def __init__(self, inner: ScriptedMonitor) -> None:
        self.inner = inner
        self.opened = False

    def verdict(self, unit):
        text = unit.text.casefold()
        opens = "checker" in text or "skip" in text or "posted city rule" in text
        if unit.kind == "claim" and opens and "\n" not in unit.text:
            if self.opened:
                return Verdict(unit_id=unit.id, status="Ok", reason="consult already opened")
            self.opened = True
            return Verdict(
                unit_id=unit.id,
                status="Ok",
                reason="named consult",
                consult_to="checker",
            )
        return self.inner.verdict(unit)

    def __getattr__(self, name):
        return getattr(self.inner, name)


def live_checker(composed: str) -> LiveLlm:
    """The checker sees the package, including the rule result."""
    return LiveLlm(
        user_prompt=(
            composed
            + "\n\nEmit one claim and one answer. Do not emit tool_intent. "
            + "Use the rule result in the package. "
            + "If the posted city rule must be followed, say that."
        ),
        timeout_s=180.0,
    )


def run_shop_chat(monitor, llm, history, question, make_checker, desk=None, task: str = TASK) -> ShopChatResult:
    """Format this chat, consult when named, and resume the same assistant."""
    desk = desk or RuleDesk()
    result = ShopChatResult()
    result.history = history
    llm.user_prompt = TURN.format(history=history, question=question)
    first = run_session(llm=llm, monitor=monitor, tool=desk)
    result.first = first
    if first.consult_to != "checker":
        if first.committed_answer:
            remember(history, question, first.committed_answer)
        return result
    composed, written = compose_consult(first, task, desk)
    result.package = composed
    consult = run_session(
        llm=make_checker(composed),
        monitor=monitor,
        tool_policy=lambda name, args: name not in written,
    )
    result.consult = consult
    if consult.committed_answer is None:
        return result
    note = next(event.payload for event in first.events if event.type == "floor.consult")
    patch = Patch(
        from_agent="A",
        target_unit_id=str(note["unit_id"]),
        rollback_to=None,
        diagnosis="consult",
        missing=consult.committed_answer,
        directive=consult.committed_answer,
    )
    resumed = run_session(
        llm=llm,
        monitor=monitor,
        resume_patch=patch,
        tool_policy=lambda name, args: name not in written,
    )
    result.resumed = resumed
    remember(history, question, resumed.committed_answer or "")
    return result


def run_live_shop(monitor: ScriptedMonitor) -> ShopChatResult:
    """Run the shop chat on the live model. The history list stays the same object."""
    monitor = _OneConsult(monitor)
    history: list = []
    assistant = LiveLlm(user_prompt="", timeout_s=180.0)
    return run_shop_chat(monitor, assistant, history, LIVE_QUESTION, live_checker)


def _load_dotenv(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    _load_dotenv()
    if not (os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")):
        print("skip live: no LLM_API_KEY")
        return 0
    monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="checker",
        consult_to="checker",
    )
    result = run_live_shop(monitor)
    last = result.history[-1].content if result.history else ""
    continued = (
        result.first is not None
        and result.first.consult_to == "checker"
        and result.resumed is not None
        and bool(result.history)
        and "skip the posted city rule" not in last.casefold()
    )
    print("consult_to", None if result.first is None else result.first.consult_to)
    print("package", TASK in result.package and "role: checker" in result.package)
    print("rule_result", f"result read_rule: {RULE_RESULT}" in result.package)
    print("first_answer", None if result.first is None else result.first.committed_answer)
    print("resumed", None if result.resumed is None else result.resumed.committed_answer)
    print("same_chat", continued)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
