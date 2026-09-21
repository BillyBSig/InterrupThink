"""LlamaIndex retriever as the retrieve tool. Not a package retriever. Not QueryEngine."""

from __future__ import annotations

from pathlib import Path

from interrupthink import SandboxWriteTool


def build_policy_retriever(*, interrupt_stale: bool, fixtures: Path, embed_model=None):
    """Official ``VectorStoreIndex.as_retriever``. One policy document in the index."""
    from llama_index.core import Document, VectorStoreIndex
    from llama_index.core.embeddings import MockEmbedding

    name = "stale.txt" if interrupt_stale else "current.txt"
    text = (Path(fixtures) / name).read_text(encoding="utf-8")
    doc = Document(text=text, metadata={"path": name})
    embed = embed_model if embed_model is not None else MockEmbedding(embed_dim=8)
    index = VectorStoreIndex.from_documents([doc], embed_model=embed)
    return index.as_retriever(similarity_top_k=1)


def live_embed_model():
    """OpenAI embeddings when the integration is installed; else MockEmbedding."""
    try:
        from llama_index.embeddings.openai import OpenAIEmbedding

        return OpenAIEmbedding()
    except ImportError:
        from llama_index.core.embeddings import MockEmbedding

        return MockEmbedding(embed_dim=8)


class LlamaIndexRetrieveTool:
    """Case-local wrap of ``retriever.retrieve``. Does not live in interrupthink."""

    def __init__(self, retriever) -> None:
        self.retriever = retriever
        self.calls: list[dict] = []
        self.retrieved: list[str] = []

    def execute(self, name: str, args: dict) -> str:
        payload = {"name": name, "args": dict(args or {})}
        self.calls.append(payload)
        if name != "retrieve":
            raise ValueError(f"unsupported retrieve tool: {name}")
        query = str((args or {}).get("query") or "refund policy")
        nodes = self.retriever.retrieve(query)
        text = nodes[0].get_content() if nodes else ""
        self.retrieved.append(text)
        return text


class RetrieveThenWriteTool:
    """One session, two names. Retrieve is LlamaIndex; write is sandbox."""

    def __init__(self, retriever, sandbox: Path | str) -> None:
        self.retrieve = LlamaIndexRetrieveTool(retriever)
        self.write = SandboxWriteTool(sandbox)
        self.calls: list[dict] = []

    def execute(self, name: str, args: dict) -> str:
        payload = {"name": name, "args": dict(args or {})}
        self.calls.append(payload)
        if name == "retrieve":
            return self.retrieve.execute(name, args)
        if name == "write":
            return self.write.execute(name, args)
        raise ValueError(f"unsupported tool: {name}")
