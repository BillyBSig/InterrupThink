"""The same assistant continues from the page stored in this folder."""

from __future__ import annotations

from llama_index.core import Document, VectorStoreIndex
from llama_index.core.embeddings import MockEmbedding

from interrupthink import Consult, LiveLlm, Patch, ScriptedMonitor, Verdict, run_session


class PageRetrieve:
    """Host retrieve. The page text is stored on the call."""

    def __init__(self, retriever) -> None:
        self.retriever = retriever
        self.calls: list[dict] = []

    def execute(self, name: str, args: dict) -> str:
        if name == "retrieve_page":
            nodes = self.retriever.retrieve(str((args or {}).get("query") or "exchange"))
            result = nodes[0].get_content() if nodes else ""
        else:
            result = "ok"
        self.calls.append({"name": name, "args": dict(args), "result": result})
        return result


def build_retriever(page: str):
    """One policy page. The retriever does not run the chat."""
    document = Document(text=page, metadata={"source": "returns-page"})
    index = VectorStoreIndex.from_documents(
        [document],
        embed_model=MockEmbedding(embed_dim=8),
    )
    return index.as_retriever(similarity_top_k=1)


class PageConsultResult:
    def __init__(self) -> None:
        self.first = None
        self.consult = None
        self.resumed = None
        self.package = ""


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
    if tool is not None and not any(call["name"] == "retrieve_page" for call in calls):
        tool.execute("retrieve_page", {"query": "exchange after 30 days"})
        calls.append(dict(tool.calls[-1]))
    note = {**note, "tool_calls": calls}
    composed = receiver_input(task, note, str(note["consult_to"]), str(note.get("reason") or ""))
    return composed, {str(call["name"]) for call in calls}


class _OneConsult:
    """Open the checker once. A later claim that mentions the checker stays put."""

    def __init__(self, inner: ScriptedMonitor) -> None:
        self.inner = inner
        self.opened = False

    def verdict(self, unit):
        if unit.kind == "claim" and "checker" in unit.text.casefold() and "\n" not in unit.text:
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
        + "\n\nEmit only XML. Retrieve the page, then one claim that asks the checker, then an answer.\n"
        + "The retrieve body is JSON on one line:\n"
        + '<step kind="tool_intent" reversible="true">'
        + '{"name":"retrieve_page","args":{"query":"exchange after 30 days"}}</step>\n'
        + '<step kind="claim">ask the checker</step>\n'
    )


def live_checker(composed: str) -> LiveLlm:
    """The checker sees the package, including the retrieved page."""
    return LiveLlm(
        user_prompt=(
            composed
            + "\n\nEmit one claim and one answer. Do not emit tool_intent. "
            + "Use only the retrieved page in the package. "
            + "If the page says exchanges after 30 days are not offered, say that and nothing further."
        ),
        timeout_s=180.0,
    )


def run_page_consult(monitor, assistant, make_checker, tool, task: str) -> PageConsultResult:
    """Consult on the retrieved page, then resume the same assistant."""
    result = PageConsultResult()
    first = run_session(llm=assistant, monitor=monitor, tool=tool)
    result.first = first
    if first.consult_to != "checker":
        return result
    composed, written = compose_consult(first, task, tool)
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
    result.resumed = run_session(
        llm=assistant,
        monitor=monitor,
        resume_patch=patch,
        tool_policy=lambda name, args: name not in written,
    )
    return result


def run_live_page(monitor: ScriptedMonitor, page: str, task: str, question: str) -> PageConsultResult:
    """Run the assistant on the live model. The page comes from the fixture."""
    monitor = _OneConsult(monitor)
    assistant = LiveLlm(user_prompt=live_question(question), timeout_s=180.0)
    tool = PageRetrieve(build_retriever(page))
    return run_page_consult(monitor, assistant, live_checker, tool, task)
