"""The same LangChain chat continues after the checker returns a patch."""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from interrupthink import Consult, LiveLlm, Patch, ScriptedMonitor, Verdict, run_session

TURN = ChatPromptTemplate.from_messages(
    [
        ("system", "You are the shop assistant. Emit only XML. Stay with this chat."),
        MessagesPlaceholder("history", optional=True),
        ("human", "{question}"),
    ]
)


class RuleDesk:
    """Host desk. The rule text is stored on the call."""

    def __init__(self, rule_result: str) -> None:
        self.calls: list[dict] = []
        self.rule_result = rule_result

    def execute(self, name: str, args: dict) -> str:
        result = self.rule_result if name == "read_rule" else "ok"
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


def live_question(question: str) -> str:
    return (
        question
        + "\n\nEmit only XML. Read the rule, then one claim that asks the checker, then an answer.\n"
        + "The rule body is JSON on one line:\n"
        + 'tool_intent reversible: ' + '{"name":"read_rule","args":{"topic":"posted city rule"}}\n'
        + 'claim: ask the checker\n'
    )


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


def run_shop_chat(monitor, llm, history, question, make_checker, desk, task: str) -> ShopChatResult:
    """Format this chat, consult when named, and resume the same assistant."""
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


def run_live_shop(monitor: ScriptedMonitor, desk, task: str, question: str) -> ShopChatResult:
    """Run the shop chat on the live model. The history list stays the same object."""
    monitor = _OneConsult(monitor)
    history: list = []
    assistant = LiveLlm(user_prompt="", timeout_s=180.0)
    return run_shop_chat(monitor, assistant, history, live_question(question), live_checker, desk, task)
