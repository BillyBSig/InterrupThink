"""The rule cookbook keeps the same chat and writes the same consult package."""

import importlib.util
import sys
from pathlib import Path

from interrupthink import FakeLlm

REPO = Path(__file__).resolve().parents[1]
CASE = REPO / "cases" / "langchain-rule"
CHECKER_ANSWER = "The posted city rule must be followed."


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
    return _load(CASE / "run.py", "langchain_rule_case_run")


def _example():
    return _load(REPO / "examples" / "langchain_rule_consult.py", "langchain_rule_consult_case_check")


def _checker(composed: str):
    visible = composed.replace("<", "[").replace(">", "]")
    tool = (
        '<step kind="tool_intent" reversible="true">'
        '{"name":"read_rule","args":{"topic":"again"}}</step>'
    )
    document = f'<step kind="claim">{visible}</step>\n{tool}\n<answer>{CHECKER_ANSWER}</answer>'
    checker = FakeLlm([document])
    checker.apply_resume(composed)
    return checker


def test_fixture_matches_the_demo_and_the_same_chat_continues(tmp_path: Path):
    case = _case()
    example = _example()
    task, rule, question = case.read_fixtures()
    assert task == example.TASK
    assert rule == example.RULE_RESULT
    assert question == example.QUESTION
    history: list = []
    assistant = FakeLlm([case.SHOP_DOCUMENT, case.CONTINUATION])
    result, payload = case.run_cookbook(
        named=True,
        assistant=assistant,
        make_checker=_checker,
        sandbox=tmp_path,
        history=history,
    )
    note = next(event.payload for event in result.first.events if event.type == "floor.consult")
    assert result.package == example.receiver_input(example.TASK, note, "checker", "named consult")
    assert f"result read_rule: {rule}" in result.package
    assert result.history is history
    assert [message.content for message in history] == [question, case.CONTINUED]
    assert payload["first_answer"] is None
    assert payload["resumed"] == case.CONTINUED
    assert payload["same_chat"] is True
    assert (tmp_path / "consult-package.txt").read_text(encoding="utf-8") == result.package
    assert assistant.request_index == 2


def test_unnamed_chat_can_keep_the_skipped_rule(tmp_path: Path):
    case = _case()
    history: list = []
    assistant = FakeLlm([case.SHOP_DOCUMENT])
    result, _payload = case.run_cookbook(
        named=False,
        assistant=assistant,
        make_checker=_checker,
        sandbox=tmp_path,
        history=history,
    )
    assert result.first.consult_to == ""
    assert result.first.committed_answer == case.BAD
    assert history[-1].content == case.BAD


def test_case_owns_the_route_and_does_not_import_the_demo():
    run_text = (CASE / "run.py").read_text(encoding="utf-8")
    graph_text = (CASE / "graph.py").read_text(encoding="utf-8")
    example = (REPO / "examples" / "langchain_rule_consult.py").read_text(encoding="utf-8")
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert "examples/" not in run_text
    assert "examples/" not in graph_text
    assert "MessagesPlaceholder" in graph_text
    assert "AgentExecutor" not in graph_text
    assert "cases/langchain-rule/run.py" in example
    assert "langchain" not in pyproject
