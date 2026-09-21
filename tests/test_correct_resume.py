"""Patch plus rollback; do not write the production file."""

import importlib.util
from pathlib import Path

from interrupthink import DummyTool, FakeLlm, JsonlLogger, ScriptedMonitor, run_session
from src.runtime.events import Patch, Verdict

REPO = Path(__file__).resolve().parents[1]


def _case():
    path = REPO / "cases" / "correct-resume" / "run.py"
    spec = importlib.util.spec_from_file_location("correct_resume_run", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _wired(ex, *, interrupt: bool, sandbox: Path):
    if interrupt:
        llm = FakeLlm([ex.WRONG_THEN_WRITE, ex.CORRECTED_THEN_WRITE])
        monitor = ex.scripted_supervisor()
    else:
        llm = FakeLlm([ex.WRONG_THEN_WRITE])
        monitor = ScriptedMonitor(trigger_kind=None)
    return ex.run_correct_resume(
        interrupt=interrupt,
        sandbox=sandbox,
        llm=llm,
        monitor=monitor,
        logger=JsonlLogger(redact=False),
    )


def test_interrupt_patch_does_not_write_production(tmp_path: Path):
    ex = _case()
    out = _wired(ex, interrupt=True, sandbox=tmp_path)
    payload = ex.analyze(out)
    assert payload["production_exists"] is False
    assert not (tmp_path / "production.txt").exists()
    assert "production.txt" not in payload["written"]
    assert out.result.interrupt_ids
    assert "floor.interrupt" in payload["event_sequence"]
    assert payload["request_count"] == 2
    assert payload["staging_exists"] is True
    assert payload["written"] == ["staging.txt"]
    assert "Wrote staging.txt" in payload["committed_answer"]
    assert "Wrote production.txt" not in payload["committed_answer"]


def test_resume_is_rollback_not_restart(tmp_path: Path):
    ex = _case()
    out = _wired(ex, interrupt=True, sandbox=tmp_path)
    payload = ex.analyze(out)
    assert payload["resume_modes"]
    assert all(mode == "rollback" for mode in payload["resume_modes"])
    prefix = payload["resume_prefix"] or ""
    assert prefix
    assert ex.STAGING_FACT in prefix
    assert "write the host file from the ticket" in prefix
    assert "<step kind=\"claim\">the ticket host is production</step>" not in prefix
    assert "production.txt" not in prefix
    assert payload["binding"] == ex.STAGING_FACT


def test_without_interrupt_writes_production(tmp_path: Path):
    ex = _case()
    out = _wired(ex, interrupt=False, sandbox=tmp_path)
    payload = ex.analyze(out)
    assert out.result.interrupt_ids == []
    assert payload["production_exists"] is True
    assert payload["staging_exists"] is False
    assert payload["written"] == ["production.txt"]
    assert (tmp_path / "production.txt").read_text(encoding="utf-8") == "deploy to production"
    assert payload["request_count"] == 1
    assert payload["resume_modes"] == []


PATCH_FACT = "write staging.txt not production"
PATCH_DOC_1 = """
<step kind="plan">write the host file from the ticket</step>
<step kind="claim">the ticket host is production</step>
<answer>Wrote production.txt</answer>
"""
PATCH_DOC_2 = """
<step kind="plan">write the host file from the ticket</step>
<step kind="claim">the ticket host is staging</step>
<answer>Wrote staging.txt</answer>
"""


class _PatchThenOk:
    """Ok until one Patch on plan, then Ok (not False+rollback)."""

    def __init__(self) -> None:
        self.held_tool_ids: list[str] = []
        self.fired = False

    def verdict(self, unit):
        if unit.kind == "answer_draft":
            return Verdict(unit_id=unit.id, status="Ok", reason="answer ok")
        if not self.fired and unit.kind == "plan":
            self.fired = True
            return Verdict(
                unit_id=unit.id,
                status="Patch",
                reason="correct host",
                patch=Patch(
                    from_agent="A",
                    target_unit_id=unit.id,
                    rollback_to=None,
                    diagnosis="wrong host",
                    missing=PATCH_FACT,
                    directive="use staging",
                ),
            )
        return Verdict(unit_id=unit.id, status="Ok", reason="pass")

    def release_tool(self, unit_id: str):
        return Verdict(unit_id=unit_id, status="Ok", reason="release")


def test_patch_aborts_and_second_request_prefix_carries_fact():
    llm = FakeLlm([PATCH_DOC_1, PATCH_DOC_2])
    llm.prefix = None
    abort_calls = {"n": 0}
    inner = llm.abort

    def _abort() -> None:
        abort_calls["n"] += 1
        inner()

    llm.abort = _abort  # type: ignore[method-assign]
    result = run_session(llm=llm, monitor=_PatchThenOk(), tool=DummyTool())
    assert abort_calls["n"] == 1
    assert result.request_count == 2
    assert result.interrupt_ids
    assert result.committed_answer == "Wrote staging.txt"
    prefix = llm.prefix or ""
    assert PATCH_FACT in prefix
    assert "the ticket host is production" not in prefix


def test_case_is_correct_then_continue_not_freeze_only():
    text = (REPO / "cases" / "correct-resume" / "run.py").read_text(encoding="utf-8")
    assert "SandboxWriteTool" in text
    assert "LiveOpenAILlm" in text
    assert "CORRECTED_THEN_WRITE" in text
    assert "DummyTool()" not in text
    assert 'resume_mode = "restart"' not in text
    assert "import git" not in text
    assert "pymongo" not in text
