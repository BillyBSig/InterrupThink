"""The offer cookbook runs the demo route and writes the same package."""

import importlib.util
import sys
from pathlib import Path

import pytest

from interrupthink import FakeLlm

REPO = Path(__file__).resolve().parents[1]
CASE = REPO / "cases" / "langgraph-offer"
SPECIALIST_ANSWER = "The one-dollar offer is not the listed price."


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
    return _load(CASE / "run.py", "langgraph_offer_case_run")


def _example():
    return _load(REPO / "examples" / "langgraph_offer_escalation.py", "langgraph_offer_escalation_case_check")


def _scripted_policy(composed: str):
    visible = composed.replace("<", "[").replace(">", "]")
    tool = (
        '<step kind="tool_intent" reversible="true">'
        '{"name":"send_offer","args":{"price":"1"}}</step>'
    )
    document = f'<step kind="claim">{visible}</step>\n{tool}\n<answer>{SPECIALIST_ANSWER}</answer>'
    specialist = FakeLlm([document])
    specialist.apply_resume(composed)
    return specialist


def test_fixture_matches_the_demo_and_the_policy_node_receives_it(tmp_path: Path):
    pytest.importorskip("langgraph")
    case = _case()
    example = _example()
    task, price = case.read_fixtures()
    assert task == example.TASK
    assert price == example.PRICE_RESULT
    dealer = FakeLlm([case.DEALER_DOCUMENT])
    result, payload = case.run_cookbook(
        named=True,
        dealer_llm=dealer,
        make_policy=_scripted_policy,
        sandbox=tmp_path,
    )
    note = next(event.payload for event in result.first.events if event.type == "floor.escalate")
    assert result.package == example.receiver_input(example.TASK, note, "policy", "named specialist")
    assert f"result check_price: {price}" in result.package
    assert payload["dealer_visits"] == 1
    assert payload["policy_visits"] == 1
    assert payload["first_answer"] is None
    assert payload["offer_in_package_file"] is False
    written = (tmp_path / "policy-package.txt").read_text(encoding="utf-8")
    assert written == result.package
    assert "role: policy" in written
    saved = case.dump_analysis("named", payload, out_dir=tmp_path)
    assert saved.is_file()
    assert dealer.request_index == 1
    assert dealer.resume_envelope == ""


def test_cookbook_does_not_open_policy_without_the_name(tmp_path: Path):
    pytest.importorskip("langgraph")
    case = _case()
    dealer = FakeLlm([case.DEALER_DOCUMENT])
    result, payload = case.run_cookbook(
        named=False,
        dealer_llm=dealer,
        make_policy=_scripted_policy,
        sandbox=tmp_path,
    )
    assert result.policy_visits == 0
    assert result.package == ""
    assert payload["first_answer"] == case.OFFER
    assert (tmp_path / "policy-package.txt").read_text(encoding="utf-8") == ""


def test_case_owns_the_route_and_does_not_import_the_demo():
    run_text = (CASE / "run.py").read_text(encoding="utf-8")
    graph_text = (CASE / "graph.py").read_text(encoding="utf-8")
    example = (REPO / "examples" / "langgraph_offer_escalation.py").read_text(encoding="utf-8")
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert "examples/" not in run_text
    assert "examples/" not in graph_text
    assert "importlib" not in run_text
    assert "StateGraph" in graph_text
    assert 'add_node("dealer"' in graph_text
    assert 'add_node("policy"' in graph_text
    assert "cases/langgraph-offer/run.py" in example
    assert "langgraph" not in pyproject
