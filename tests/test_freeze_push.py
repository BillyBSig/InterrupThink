"""Third dummy app: freeze + push. No real git. No API key."""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _example():
    path = REPO / "examples" / "dummy" / "freeze_push_dummy.py"
    spec = importlib.util.spec_from_file_location("freeze_push_dummy", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_interrupt_blocks_dummy_push():
    result, tool = _example().run_freeze_push(interrupt=True)
    assert tool.calls == []
    assert result.interrupt_ids
    assert result.committed_answer == "Did not push. Freeze still holds."
    resumes = [r for r in result.log_records if r.get("event") == "floor.resume"]
    assert resumes
    assert all(r.get("mode") == "rollback" for r in resumes)


def test_without_interrupt_dummy_push_runs():
    result, tool = _example().run_freeze_push(interrupt=False)
    assert result.interrupt_ids == []
    assert tool.calls == [{"name": "push", "args": {"remote": "origin", "branch": "main"}}]
    assert result.committed_answer == "Pushed hotfix to origin/main."


def test_example_is_library_dummy_not_git():
    text = (REPO / "examples" / "dummy" / "freeze_push_dummy.py").read_text(encoding="utf-8")
    assert "from src." not in text
    assert "run_staging_case" not in text
    assert "OPENAI" not in text
    assert "subprocess" not in text
    assert "git " not in text
    assert "from interrupthink import DummyTool, FakeLlm, ScriptedMonitor, run_session" in text
