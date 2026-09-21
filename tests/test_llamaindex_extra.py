"""LlamaIndex retriever as retrieve step; supervisor cuts a stale claim. Optional extra, not a package."""

import importlib.util
import sys
from pathlib import Path

import pytest

from interrupthink import FakeLlm, ScriptedMonitor

REPO = Path(__file__).resolve().parents[1]
CASE = REPO / "cases" / "llamaindex-retrieve"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _purge_case_top_level_modules() -> None:
    for name in ("config", "tools", "graph", "run"):
        sys.modules.pop(name, None)


def _case():
    if str(CASE) not in sys.path:
        sys.path.insert(0, str(CASE))
    _purge_case_top_level_modules()
    return _load(CASE / "run.py", "llamaindex_retrieve_run")


def _config():
    if str(CASE) not in sys.path:
        sys.path.insert(0, str(CASE))
    return _load(CASE / "config.py", "llamaindex_retrieve_config")


def _wired(ex, *, interrupt_stale: bool, sandbox: Path):
    pytest.importorskip("llama_index.core")
    from llama_index.core.embeddings import MockEmbedding

    cfg = _config()
    embed = MockEmbedding(embed_dim=8)
    if interrupt_stale:
        llm = FakeLlm([cfg.STALE_THEN_ACT, cfg.STALE_STOPPED])
        monitor = ScriptedMonitor(
            trigger_kind="premise",
            trigger_contains="retrieved policy is in force",
        )
    else:
        llm = FakeLlm([cfg.CURRENT_THEN_ACT])
        monitor = ScriptedMonitor(trigger_kind=None)
    return ex.run_llamaindex_retrieve(
        interrupt_stale=interrupt_stale,
        sandbox=sandbox,
        llm=llm,
        monitor=monitor,
        embed_model=embed,
    )


def test_llamaindex_is_not_a_lock_dependency():
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    lock = (REPO / "uv.lock").read_text(encoding="utf-8")
    assert "llama-index" not in pyproject
    assert "llama_index" not in pyproject
    assert "name = \"llama-index\"" not in lock
    assert "name = \"llama-index-core\"" not in lock
    assert "name = \"llama-index-llms-openai\"" not in lock


def test_stale_retrieve_does_not_write_notice(tmp_path: Path):
    ex = _case()
    out = _wired(ex, interrupt_stale=True, sandbox=tmp_path)
    payload = ex.analyze(out)
    assert payload["retrieve_calls"] == [
        {"name": "retrieve", "args": {"query": "customer refund policy"}}
    ]
    assert payload["write_calls"] == []
    assert payload["notice_exists"] is False
    assert not (tmp_path / "notice.txt").exists()
    assert out.result.interrupt_ids
    assert "2019" in (payload["retrieved"][0] if payload["retrieved"] else "")
    assert payload["retriever_class"] == "VectorIndexRetriever"
    assert "tool.execute" in payload["event_sequence"]
    assert payload["tool_calls"] == payload["retrieve_calls"]


def test_current_retrieve_writes_one_notice(tmp_path: Path):
    ex = _case()
    out = _wired(ex, interrupt_stale=False, sandbox=tmp_path)
    payload = ex.analyze(out)
    assert out.result.interrupt_ids == []
    assert payload["retrieve_calls"] == [
        {"name": "retrieve", "args": {"query": "customer refund policy"}}
    ]
    assert payload["write_calls"] == [
        {
            "name": "write",
            "args": {"path": "notice.txt", "content": "refunds allowed within 30 days"},
        }
    ]
    assert payload["notice_exists"] is True
    assert (tmp_path / "notice.txt").read_text(encoding="utf-8") == "refunds allowed within 30 days"
    assert "2026" in (payload["retrieved"][0] if payload["retrieved"] else "")
    names = [c["name"] for c in payload["tool_calls"]]
    assert names == ["retrieve", "write"]


def test_one_session_not_query_engine_think(tmp_path: Path):
    ex = _case()
    out = _wired(ex, interrupt_stale=False, sandbox=tmp_path)
    graph = (CASE / "graph.py").read_text(encoding="utf-8")
    tools = (CASE / "tools.py").read_text(encoding="utf-8")
    assert graph.count("run_session(") == 1
    assert "as_query_engine" not in graph
    assert "as_query_engine" not in tools
    assert "as_retriever" in tools
    assert out.result.request_count == 1


def test_case_is_llamaindex_extra_not_package_retriever():
    tools = (CASE / "tools.py").read_text(encoding="utf-8")
    public = (REPO / "interrupthink" / "__init__.py").read_text(encoding="utf-8")
    assert "from llama_index.core import Document, VectorStoreIndex" in tools
    assert "LlamaIndexRetrieveTool" not in public
    assert "build_policy_retriever" not in public
    assert "run_llamaindex_retrieve" not in public
    assert "import qdrant" not in tools
    assert "from qdrant" not in tools


def test_example_calls_interruptible_not_the_case():
    example = (REPO / "examples" / "llamaindex_retrieve_node.py").read_text(encoding="utf-8")
    assert "from interrupthink import" in example
    assert "LiveOpenAILlm" in example
    assert "from llama_index.llms.openai import OpenAI" in example
    assert "from llama_index.embeddings.openai import OpenAIEmbedding" in example
    assert "as_retriever" in example
    assert "as_query_engine" not in example
    assert "importlib" not in example
    assert "spec_from_file_location" not in example
    assert "FakeLlm" not in example
    assert "run_llamaindex_retrieve" not in example
    assert "llamaindex-retrieve" not in example or "cases/llamaindex-retrieve" in example
