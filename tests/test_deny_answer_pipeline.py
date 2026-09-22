"""Stop an unsupported answer in a native host pipeline. LangGraph extra skips if missing."""

import importlib.util
from pathlib import Path

import pytest

from interrupthink import FakeLlm, ScriptedMonitor

REPO = Path(__file__).resolve().parents[1]


def _case():
    path = REPO / "cases" / "deny-answer-pipeline" / "run.py"
    spec = importlib.util.spec_from_file_location("deny_answer_pipeline_run", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _wired(ex, *, interrupt: bool, sandbox: Path):
    monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains=ex.FALSE_POLICY,
    )
    if interrupt:
        answer_llm = FakeLlm([ex.FALSE_CLAIM, ex.FALSE_STOPPED])
        send_llm = None
    else:
        answer_llm = FakeLlm([ex.TRUE_CLAIM])
        send_llm = FakeLlm([ex._send_xml(ex.ALLOWED)])
    return ex.run_deny_answer_pipeline(
        interrupt=interrupt,
        sandbox=sandbox,
        monitor=monitor,
        answer_llm=answer_llm,
        send_llm=send_llm,
    )


def test_interrupt_leaves_outbox_empty(tmp_path: Path):
    ex = _case()
    out = _wired(ex, interrupt=True, sandbox=tmp_path)
    payload = ex.analyze(out)
    assert payload["outbox_exists"] is False
    assert not (tmp_path / "outbox.txt").exists()
    assert payload["send_calls"] == []
    assert out.send_result is None
    assert payload["session_count"] == 1
    assert out.answer_result.interrupt_ids
    assert payload["answer_calls"] == []
    answer = payload["answer_text"] or ""
    assert ex.FALSE_POLICY not in answer
    assert "Did not send" in answer


def test_without_interrupt_writes_one_outbox_line(tmp_path: Path):
    ex = _case()
    out = _wired(ex, interrupt=False, sandbox=tmp_path)
    payload = ex.analyze(out)
    assert out.answer_result.interrupt_ids == []
    assert payload["session_count"] == 2
    assert payload["session_tools"] == ["answer", "send"]
    assert payload["outbox_exists"] is True
    assert payload["outbox_text"] == ex.ALLOWED
    assert payload["forwarded"] == ex.ALLOWED
    assert out.send_result is not None
    assert payload["send_calls"] == [
        {"name": "write", "args": {"path": "outbox.txt", "content": ex.ALLOWED}}
    ]


def test_langgraph_skip_or_t1_if_present(tmp_path: Path):
    pytest.importorskip("langgraph")
    native = _case()
    path = REPO / "cases" / "deny-answer-pipeline" / "langgraph_host.py"
    spec = importlib.util.spec_from_file_location("deny_answer_langgraph_host", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    leftover = tmp_path / "outbox.txt"
    if leftover.is_file():
        leftover.unlink()
    monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains=native.FALSE_POLICY,
    )
    out = mod.run_deny_answer_langgraph(
        interrupt=True,
        sandbox=tmp_path,
        native=native,
        monitor=monitor,
        answer_llm=FakeLlm([native.FALSE_CLAIM, native.FALSE_STOPPED]),
    )
    payload = native.analyze(out)
    assert payload["outbox_exists"] is False
    assert out.send_result is None
    assert out.answer_result.interrupt_ids


def test_native_host_not_smtp_or_required_langgraph():
    text = (REPO / "cases" / "deny-answer-pipeline" / "run.py").read_text(encoding="utf-8")
    public = (REPO / "interrupthink" / "__init__.py").read_text(encoding="utf-8")
    assert "from interrupthink import" in text
    assert "run_session" in text
    assert "SandboxWriteTool" in text
    assert "LiveLlm" in text
    assert "DummyTool()" not in text
    assert "smtplib" not in text
    assert "import langgraph" not in text
    assert "from langgraph" not in text
    assert "import crewai" not in text
    assert "AnswerTool" not in public
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert "langgraph" not in pyproject
