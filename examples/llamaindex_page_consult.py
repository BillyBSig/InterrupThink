"""The same assistant continues from the retrieved page.

Scenario
    A customer asks about an exchange. The host retrieves one policy page.
    The supervisor names ``checker`` before an answer beyond that page is
    committed. The checker sees the page in the package. The patch comes
    back to the same assistant.

Expected
    The answer does not go beyond the retrieved page.
    The index is only the retrieve tool. It does not continue the chat.

Usage (repo root)::

    pip install -e . && pip install llama-index   # venv; do not uv-add
    python3 examples/llamaindex_page_consult.py

Cookbook: ``cases/llamaindex-page/run.py``.
"""

from __future__ import annotations

import os
from pathlib import Path

from llama_index.core import Document, VectorStoreIndex
from llama_index.core.embeddings import MockEmbedding

from interrupthink import Consult, LiveLlm, Patch, ScriptedMonitor, Verdict, run_session

TASK = "Answer the customer's exchange question only from the retrieved policy page."
QUESTION = "Can I exchange this after 30 days?"
PAGE = (
    "Returns are accepted within 30 days with a receipt. "
    "Exchanges after 30 days are not offered."
)
LIVE_QUESTION = (
    QUESTION
    + "\n\nEmit only XML. Retrieve the page, then one claim that asks the checker, then an answer.\n"
    + "The retrieve body is JSON on one line:\n"
    + 'tool_intent reversible: ' + '{"name":"retrieve_page","args":{"query":"exchange after 30 days"}}\n'
    + 'claim: ask the checker\n'
)


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


def build_retriever(page: str = PAGE):
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


def run_page_consult(monitor, assistant, make_checker, tool=None, task: str = TASK) -> PageConsultResult:
    """Consult on the retrieved page, then resume the same assistant."""
    tool = tool or PageRetrieve(build_retriever())
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


def run_live_page(monitor: ScriptedMonitor) -> PageConsultResult:
    """Run the assistant on the live model. The page comes from the index."""
    monitor = _OneConsult(monitor)
    assistant = LiveLlm(user_prompt=LIVE_QUESTION, timeout_s=180.0)
    return run_page_consult(monitor, assistant, live_checker)


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
    result = run_live_page(monitor)
    print("consult_to", None if result.first is None else result.first.consult_to)
    print("package", TASK in result.package and "role: checker" in result.package)
    print("page_result", PAGE in result.package)
    print("first_answer", None if result.first is None else result.first.committed_answer)
    print("resumed", None if result.resumed is None else result.resumed.committed_answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
