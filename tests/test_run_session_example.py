"""User wires run_session from public imports. Dummy publish. No API key."""

import importlib.util
from pathlib import Path

from interrupthink import DummyTool, FakeLlm, ScriptedMonitor, run_session

REPO = Path(__file__).resolve().parents[1]


def _example():
    path = REPO / "examples" / "run_session_dummy.py"
    spec = importlib.util.spec_from_file_location("run_session_dummy", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_user_wires_interrupt_blocks_publish():
    result, tool = _example().run_user_session(interrupt=True)
    assert tool.calls == []
    assert result.interrupt_ids
    resumes = [r for r in result.log_records if r.get("event") == "floor.resume"]
    assert resumes
    assert all(r.get("mode") == "rollback" for r in resumes)


def test_user_wires_without_interrupt_publishes():
    result, tool = _example().run_user_session(interrupt=False)
    assert result.interrupt_ids == []
    assert tool.calls == [{"name": "publish", "args": {"doc": "changelog"}}]


def test_example_imports_only_interruptible():
    text = (REPO / "examples" / "run_session_dummy.py").read_text(encoding="utf-8")
    assert "from src." not in text
    assert "run_staging_case" not in text
    assert "OPENAI" not in text
    assert "from interrupthink import DummyTool, FakeLlm, ScriptedMonitor, run_session" in text


def test_public_symbols_suffice_without_helper():
    tool = DummyTool()
    llm = FakeLlm(
        [
            '<step kind="plan">x</step>'
            '<step kind="premise">already approved</step>'
            "<answer>published</answer>",
            '<step kind="claim">not approved</step><answer>stopped</answer>',
        ]
    )
    monitor = ScriptedMonitor(trigger_kind="premise", trigger_contains="already approved")
    result = run_session(llm=llm, monitor=monitor, tool=tool)
    assert result.interrupt_ids
    assert tool.calls == []
