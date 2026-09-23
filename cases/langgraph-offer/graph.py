"""Two LangGraph nodes. The host package is the edge between them."""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from interrupthink import Escalation, LiveLlm, ScriptedMonitor, Verdict, run_session

OFFER_RESULT = "sent"


class OfferDesk:
    """Host desk. The price check and any offer are stored on the call."""

    def __init__(self, price_result: str) -> None:
        self.calls: list[dict] = []
        self.price_result = price_result

    def execute(self, name: str, args: dict) -> str:
        if name == "check_price":
            result = self.price_result
        elif name == "send_offer":
            result = OFFER_RESULT
        else:
            result = "ok"
        self.calls.append({"name": name, "args": dict(args), "result": result})
        return result


class OfferState(TypedDict, total=False):
    escalated: bool
    package: str


class OfferGraphResult:
    """What the two nodes did. The graph state itself stays the package text."""

    def __init__(self) -> None:
        self.first = None
        self.second = None
        self.package = ""
        self.written: set[str] = set()
        self.dealer_visits = 0
        self.policy_visits = 0


def receiver_input(task: str, note: dict, role: str, reason: str) -> str:
    """Compose the policy node's input from the imported package."""
    noted = dict(note)
    noted["escalate_to"] = role
    noted["reason"] = reason
    return Escalation.from_note(task, noted).text()


def compose_escalation(first, task: str, tool=None) -> tuple[str, set[str]]:
    """Build the package after the supervisor names policy. Does not open a session."""
    if first.escalate_to != "policy":
        return "", set()
    note = next(event.payload for event in first.events if event.type == "floor.escalate")
    calls = [dict(call) for call in note["tool_calls"]]
    if tool is not None and not any(call["name"] == "check_price" for call in calls):
        tool.execute("check_price", {"model": "Tahoe"})
        calls.append(dict(tool.calls[-1]))
    note = {**note, "tool_calls": calls}
    composed = receiver_input(task, note, str(note["escalate_to"]), str(note.get("reason") or ""))
    return composed, {str(call["name"]) for call in calls}


def run_policy_session(composed: str, written: set[str], monitor, make_policy):
    """Run the named specialist. The offer tool is not sent again."""
    blocked = set(written)
    blocked.add("send_offer")
    return run_session(
        llm=make_policy(composed),
        monitor=monitor,
        tool_policy=lambda name, args: name not in blocked,
    )


class _OneEscalation:
    """Open policy once. A later claim that mentions policy stays put."""

    def __init__(self, inner: ScriptedMonitor) -> None:
        self.inner = inner
        self.opened = False

    def verdict(self, unit):
        text = unit.text.casefold()
        if unit.kind == "claim" and "policy" in text and "\n" not in unit.text:
            if self.opened:
                return Verdict(unit_id=unit.id, status="Ok", reason="escalation already opened")
            self.opened = True
            return Verdict(
                unit_id=unit.id,
                status="Ok",
                reason="named specialist",
                escalate_to="policy",
            )
        return self.inner.verdict(unit)

    def __getattr__(self, name):
        return getattr(self.inner, name)


def live_task(task: str) -> str:
    """The dealer prompt. The price check is one JSON step."""
    return (
        task
        + "\n\nEmit only XML. Check the listed price, then one claim that asks policy, then an answer.\n"
        + "The price body is JSON on one line:\n"
        + '<step kind="tool_intent" reversible="true">'
        + '{"name":"check_price","args":{"model":"Tahoe"}}</step>\n'
        + '<step kind="claim">ask policy</step>\n'
    )


def live_specialist(composed: str) -> LiveLlm:
    """The policy node sees the package, including the price result."""
    return LiveLlm(
        user_prompt=(
            composed
            + "\n\nEmit one claim and one answer. Do not emit tool_intent. "
            + "Use the price result in the package. "
            + "If the listed price is not one dollar, say the one-dollar offer is not the listed price."
        ),
        timeout_s=180.0,
    )


def run_offer_graph(monitor, dealer_llm, make_policy, desk, task: str) -> OfferGraphResult:
    """Two nodes. The edge carries the host package. The graph does not name a specialist."""
    result = OfferGraphResult()

    def dealer(state: OfferState) -> OfferState:
        result.dealer_visits += 1
        first = run_session(llm=dealer_llm, monitor=monitor, tool=desk)
        result.first = first
        if first.escalate_to != "policy":
            return {"escalated": False, "package": ""}
        composed, written = compose_escalation(first, task, desk)
        result.package = composed
        result.written = written
        return {"escalated": True, "package": composed}

    def policy(state: OfferState) -> OfferState:
        result.policy_visits += 1
        result.second = run_policy_session(
            state.get("package") or "",
            result.written,
            monitor,
            make_policy,
        )
        return {}

    def route(state: OfferState) -> str:
        """Forward the host flag. The graph does not choose the specialist."""
        return "policy" if state.get("escalated") else END

    graph = StateGraph(OfferState)
    graph.add_node("dealer", dealer)
    graph.add_node("policy", policy)
    graph.add_edge(START, "dealer")
    graph.add_conditional_edges("dealer", route, {"policy": "policy", END: END})
    graph.add_edge("policy", END)
    graph.compile().invoke({"escalated": False, "package": ""})
    return result


def run_live_offer(monitor: ScriptedMonitor, desk, task: str) -> OfferGraphResult:
    """Run the dealer node and, when named, the policy node on the live model."""
    monitor = _OneEscalation(monitor)
    dealer = LiveLlm(user_prompt=live_task(task), timeout_s=180.0)
    return run_offer_graph(monitor, dealer, live_specialist, desk, task)
