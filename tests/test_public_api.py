import interrupthink
import pytest
from interrupthink import DummyTool, FakeLlm, JsonlLogger, ScriptedMonitor, parse_steps, run_session


def test_public_exports_match_hygiene_list():
    assert interrupthink.__all__ == list(interrupthink.PUBLIC_API)
    for name in interrupthink.PUBLIC_API:
        assert hasattr(interrupthink, name)


def test_run_path_is_not_on_facade():
    assert "run_path" not in interrupthink.PUBLIC_API
    assert "run_path" not in interrupthink.__all__
    assert not hasattr(interrupthink, "run_path")
    with pytest.raises(ImportError):
        from interrupthink import run_path  # noqa: F401


def test_run_session_is_on_facade(tmp_path):
    result = run_session(
        llm=FakeLlm(['<step kind="plan">x</step><answer>ok</answer>']),
        monitor=ScriptedMonitor(trigger_kind=None),
        tool=DummyTool(),
        logger=JsonlLogger(tmp_path / "s.jsonl"),
    )
    assert result.committed_answer == "ok"


def test_parse_steps_exported():
    doc = parse_steps('<step kind="plan">x</step><answer>y</answer>')
    assert doc.units[0].kind == "plan"
    assert doc.answer == "y"


def test_fake_llm_is_public():
    assert FakeLlm
