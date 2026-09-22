"""run_session inside a LangChain chat turn. Optional extra, not a package."""

import importlib.util
import sys
from pathlib import Path

import pytest

from interrupthink import FakeLlm, ScriptedMonitor

REPO = Path(__file__).resolve().parents[1]
CASE = REPO / "cases" / "langchain-chat"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _purge_case_top_level_modules() -> None:
    for name in ("config", "tools", "agents", "chat", "run"):
        sys.modules.pop(name, None)


def _case():
    if str(CASE) not in sys.path:
        sys.path.insert(0, str(CASE))
    _purge_case_top_level_modules()
    return _load(CASE / "run.py", "langchain_chat_run")


def _config():
    if str(CASE) not in sys.path:
        sys.path.insert(0, str(CASE))
    return _load(CASE / "config.py", "langchain_chat_config")


def _scripted(ex, *, interrupt: bool):
    cfg = _config()
    if interrupt:
        llm = FakeLlm([cfg.FALSE_CLAIM, cfg.FALSE_STOPPED, cfg.CONFIRM_OK])
        monitor = ScriptedMonitor(
            trigger_kind="claim",
            trigger_contains="one device per subscription",
        )
    else:
        llm = FakeLlm([cfg.TRUE_CLAIM, cfg.CONFIRM_OK])
        monitor = ScriptedMonitor(trigger_kind=None)
    return llm, monitor


def test_langchain_is_not_a_lock_dependency():
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    lock = (REPO / "uv.lock").read_text(encoding="utf-8")
    assert "langchain" not in pyproject
    assert "langchain-openai" not in pyproject
    assert "langchain_core" not in pyproject
    assert "name = \"langchain\"" not in lock
    assert "name = \"langchain-core\"" not in lock
    assert "name = \"langchain-openai\"" not in lock


def test_interrupt_does_not_publish_false_policy(tmp_path: Path):
    pytest.importorskip("langchain_core")
    ex = _case()
    llm, monitor = _scripted(ex, interrupt=True)
    payload = ex.run_chat(interrupt=True, sandbox=tmp_path, llm=llm, monitor=monitor)
    assert payload["turn1_interrupt_ids"]
    assert payload["false_policy_in_history"] is False
    assert payload["false_policy_in_reply"] is False
    assert "one device per subscription" not in " ".join(payload["committed_answers"])
    assert "Did not send" in payload["committed_answers"][0]
    assert payload["history_len"] == 4
    assert payload["reply_exists"] is True


def test_without_interrupt_publishes_allowed_reply(tmp_path: Path):
    pytest.importorskip("langchain_core")
    ex = _case()
    llm, monitor = _scripted(ex, interrupt=False)
    payload = ex.run_chat(interrupt=False, sandbox=tmp_path, llm=llm, monitor=monitor)
    assert payload["interrupt_ids"] == []
    assert payload["false_policy_in_history"] is False
    assert payload["reply_exists"] is True
    assert "more than one device" in payload["reply_text"].lower()
    assert payload["history_len"] == 4


def test_cookbook_does_not_present_fake_llm():
    chat = (CASE / "chat.py").read_text(encoding="utf-8")
    run = (CASE / "run.py").read_text(encoding="utf-8")
    readme = (CASE / "README.md").read_text(encoding="utf-8")
    example = (REPO / "examples" / "langchain_chat.py").read_text(encoding="utf-8")
    public = (REPO / "interrupthink" / "__init__.py").read_text(encoding="utf-8")
    for text in (chat, run, readme):
        assert "FakeLlm" not in text
        assert "ScriptedMonitor" not in text
        assert "--mock" not in text
    assert "from interrupthink import" in example
    assert "LiveLlm" in example
    assert "run_session" in example
    assert "MessagesPlaceholder" in example
    assert "importlib" not in example
    assert "spec_from_file_location" not in example
    assert "FakeLlm" not in example
    assert "run_chat" in chat
    assert "MessagesPlaceholder" in chat
    assert "LiveLlm" in chat
    assert "run_chat" not in public
    assert "interruptible-langchain" not in chat
    assert "from langgraph" not in chat
    assert "AgentExecutor(" not in chat
    assert "smtplib" not in chat
