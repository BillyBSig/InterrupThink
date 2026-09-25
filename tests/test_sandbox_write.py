"""Real sandbox write blocked when freeze premise is false."""

import importlib.util
from pathlib import Path

import pytest

from interrupthink import FakeLlm, SandboxWriteTool, ScriptedMonitor
from interrupthink.providers.live import load_dotenv

REPO = Path(__file__).resolve().parents[1]


def _example():
    path = REPO / "cases" / "freeze-write" / "run.py"
    spec = importlib.util.spec_from_file_location("freeze_write_run", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _wired(ex, *, interrupt: bool, root: Path):
    if interrupt:
        llm = FakeLlm([ex.WRITE_WRONG, ex.WRITE_STOPPED])
        monitor = ScriptedMonitor(
            trigger_kind="premise",
            trigger_contains="code freeze is over",
        )
    else:
        llm = FakeLlm([ex.WRITE_WRONG])
        monitor = ScriptedMonitor(trigger_kind=None)
    return ex.run_sandbox_write(interrupt=interrupt, root=root, llm=llm, monitor=monitor)


def test_interrupt_does_not_write_hotfix(tmp_path: Path):
    ex = _example()
    result, tool = _wired(ex, interrupt=True, root=tmp_path)
    analysis = ex.analyze(result, tool)
    assert analysis["hotfix_exists"] is False
    assert analysis["written"] == []
    assert tool.calls == []
    assert result.interrupt_ids
    assert result.committed_answer == "Did not write. Freeze still holds."
    assert "floor.interrupt" in analysis["event_sequence"]
    assert "tool.execute" not in analysis["event_sequence"]
    resumes = [r for r in result.log_records if r.get("event") == "floor.resume"]
    assert resumes and all(r.get("mode") == "rollback" for r in resumes)


def test_without_interrupt_writes_hotfix(tmp_path: Path):
    ex = _example()
    result, tool = _wired(ex, interrupt=False, root=tmp_path)
    analysis = ex.analyze(result, tool)
    assert result.interrupt_ids == []
    assert tool.calls == [
        {"name": "write", "args": {"path": "hotfix.txt", "content": "hotfix for main"}}
    ]
    assert analysis["written"] == ["hotfix.txt"]
    assert analysis["hotfix_exists"] is True
    assert (tmp_path / "hotfix.txt").read_text(encoding="utf-8") == "hotfix for main"
    assert "tool.execute" in analysis["event_sequence"]


def test_path_outside_sandbox_rejected(tmp_path: Path):
    tool = SandboxWriteTool(tmp_path)
    with pytest.raises(ValueError, match="escapes sandbox"):
        tool.execute("write", {"path": "../outside.txt", "content": "nope"})
    assert tool.written == []
    assert tool.rejected
    assert not (tmp_path.parent / "outside.txt").exists()


def test_example_uses_sandbox_tool_not_dummy():
    text = (REPO / "cases" / "freeze-write" / "run.py").read_text(encoding="utf-8")
    assert "from interrupthink import" in text
    assert "SandboxWriteTool" in text
    assert "LiveLlm" in text
    assert "class DummyTool" not in text
    assert "DummyTool()" not in text
    assert "import git" not in text
    assert "subprocess" not in text


def test_analyze_dumps_json(tmp_path: Path):
    ex = _example()
    result, tool = _wired(ex, interrupt=True, root=tmp_path)
    path = ex.dump_analysis("unit", ex.analyze(result, tool), out_dir=tmp_path / "out")
    assert path.is_file()
    payload = path.read_text(encoding="utf-8")
    assert "event_sequence" in payload
    assert "interrupt_ids" in payload


def test_live_interrupt_optional_and_dumped(tmp_path: Path):
    """Does not gate the sandbox-write case. Records a trace if personal .env keys exist."""
    ex = _example()
    load_dotenv()
    if not ex._has_live_key():
        pytest.skip("no OPENAI_API_KEY / LLM_API_KEY")
    result, tool = ex.run_sandbox_write_live(interrupt=True, root=tmp_path)
    analysis = ex.analyze(result, tool)
    path = ex.dump_analysis("live_interrupt", analysis, out_dir=tmp_path / "live")
    assert path.is_file()
    assert "event_sequence" in path.read_text(encoding="utf-8")
