"""The order cookbook gives the counter the same package and does not place the order."""

import importlib.util
import sys
from pathlib import Path

import pytest

from interrupthink import FakeLlm

REPO = Path(__file__).resolve().parents[1]
CASE = REPO / "cases" / "crewai-order"
SPECIALIST_ANSWER = "The cone with bacon is not on the menu."


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _case():
    if str(CASE) not in sys.path:
        sys.path.insert(0, str(CASE))
    for name in ("config", "graph"):
        sys.modules.pop(name, None)
    return _load(CASE / "run.py", "crewai_order_case_run")


def _example():
    return _load(REPO / "examples" / "crewai_order_escalation.py", "crewai_order_escalation_case_check")


def _counter(composed: str):
    visible = composed.replace("<", "[").replace(">", "]")
    tool = (
        '<step kind="tool_intent" reversible="true">'
        '{"name":"place_order","args":{"item":"cone with bacon"}}</step>'
    )
    document = f'<step kind="claim">{visible}</step>\n{tool}\n<answer>{SPECIALIST_ANSWER}</answer>'
    specialist = FakeLlm([document])
    specialist.apply_resume(composed)
    return specialist


def test_fixture_matches_the_demo_and_the_counter_receives_it(tmp_path: Path):
    pytest.importorskip("crewai")
    case = _case()
    example = _example()
    task, transcript, menu = case.read_fixtures()
    assert task == example.TASK
    assert transcript == example.TRANSCRIPT
    assert menu == example.ORDER_RESULT
    taker = FakeLlm([case.ORDER_DOCUMENT])
    result, payload, desk = case.run_cookbook(
        named=True,
        taker_llm=taker,
        make_counter=_counter,
        sandbox=tmp_path,
    )
    note = next(event.payload for event in result.first.events if event.type == "floor.escalate")
    assert result.package == example.receiver_input(example.TASK, note, "counter", "named specialist")
    assert result.counter_task.description == result.package
    assert f"result read_order: {menu}" in result.package
    assert payload["counter_ran"] is True
    assert payload["first_answer"] is None
    assert [call["name"] for call in desk.calls] == ["read_order"]
    assert (tmp_path / "order-package.txt").read_text(encoding="utf-8") == result.package
    assert taker.resume_envelope == ""


def test_unnamed_taker_does_not_run_the_counter(tmp_path: Path):
    pytest.importorskip("crewai")
    case = _case()
    taker = FakeLlm([case.ORDER_DOCUMENT])
    result, payload, desk = case.run_cookbook(
        named=False,
        taker_llm=taker,
        make_counter=_counter,
        sandbox=tmp_path,
    )
    assert result.counter_ran is False
    assert payload["first_answer"] == case.BAD
    assert [call["name"] for call in desk.calls] == ["read_order"]


def test_case_owns_the_route_and_does_not_import_the_demo():
    run_text = (CASE / "run.py").read_text(encoding="utf-8")
    graph_text = (CASE / "graph.py").read_text(encoding="utf-8")
    example = (REPO / "examples" / "crewai_order_escalation.py").read_text(encoding="utf-8")
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert "examples/" not in run_text
    assert "examples/" not in graph_text
    assert "allow_delegation=False" in graph_text
    assert "kickoff(" not in graph_text
    assert "cases/crewai-order/run.py" in example
    assert "crewai" not in pyproject
