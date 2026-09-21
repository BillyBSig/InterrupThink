"""False policy claim must not reach outbox. Interrupt on claim, not only tool."""

import importlib.util
from pathlib import Path

from interrupthink import FakeLlm, ScriptedMonitor

REPO = Path(__file__).resolve().parents[1]


def _case():
    path = REPO / "cases" / "false-policy" / "run.py"
    spec = importlib.util.spec_from_file_location("false_policy_run", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _wired(ex, *, interrupt: bool, sandbox: Path):
    if interrupt:
        llm = FakeLlm([ex.FALSE_THEN_SEND, ex.FALSE_STOPPED])
        monitor = ScriptedMonitor(
            trigger_kind="claim",
            trigger_contains=ex.FALSE_POLICY,
        )
    else:
        llm = FakeLlm([ex.TRUE_THEN_SEND])
        monitor = ScriptedMonitor(trigger_kind=None)
    return ex.run_false_policy(interrupt=interrupt, sandbox=sandbox, llm=llm, monitor=monitor)


def test_false_claim_does_not_write_outbox(tmp_path: Path):
    ex = _case()
    out = _wired(ex, interrupt=True, sandbox=tmp_path)
    payload = ex.analyze(out)
    assert payload["outbox_exists"] is False
    assert payload["tool_calls"] == []
    assert not (tmp_path / "outbox.txt").exists()
    assert out.result.interrupt_ids
    assert "claim" in payload["unit_kinds"]
    assert "tool_intent" not in payload["unit_kinds"]
    assert "tool.execute" not in payload["event_sequence"]
    answer = payload["committed_answer"]
    assert "one device per subscription" not in answer
    assert "Did not send" in answer


def test_allowed_claim_writes_one_outbox_line(tmp_path: Path):
    ex = _case()
    out = _wired(ex, interrupt=False, sandbox=tmp_path)
    payload = ex.analyze(out)
    assert out.result.interrupt_ids == []
    assert payload["outbox_exists"] is True
    assert payload["outbox_text"] == "multi-device is allowed on this plan"
    assert payload["tool_calls"] == [
        {
            "name": "write",
            "args": {"path": "outbox.txt", "content": "multi-device is allowed on this plan"},
        }
    ]
    assert "claim" in payload["unit_kinds"]
    assert "tool_intent" in payload["unit_kinds"]


def test_case_is_claim_gate_not_smtp_or_classifier():
    text = (REPO / "cases" / "false-policy" / "run.py").read_text(encoding="utf-8")
    assert "from interrupthink import" in text
    assert "SandboxWriteTool" in text
    assert "LiveOpenAILlm" in text
    assert "FALSE_POLICY" in text
    assert "DummyTool()" not in text
    assert "smtplib" not in text
    assert "import openai" not in text
    assert "from nsfw" not in text
    assert "import nsfw" not in text
    assert "import langgraph" not in text
