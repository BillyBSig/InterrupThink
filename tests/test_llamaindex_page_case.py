"""The page cookbook gives the checker the fixture page and resumes the same assistant."""

import importlib.util
import sys
from pathlib import Path

import pytest

from interrupthink import FakeLlm

REPO = Path(__file__).resolve().parents[1]
CASE = REPO / "cases" / "llamaindex-page"
CHECKER_ANSWER = "Exchanges after 30 days are not offered."


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
    return _load(CASE / "run.py", "llamaindex_page_case_run")


def _example():
    return _load(REPO / "examples" / "llamaindex_page_consult.py", "llamaindex_page_consult_case_check")


def _checker(composed: str):
    visible = composed.replace("<", "[").replace(">", "]")
    tool = (
        '<step kind="tool_intent" reversible="true">'
        '{"name":"retrieve_page","args":{"query":"again"}}</step>'
    )
    document = f'<step kind="claim">{visible}</step>\n{tool}\n<answer>{CHECKER_ANSWER}</answer>'
    checker = FakeLlm([document])
    checker.apply_resume(composed)
    return checker


def test_fixture_matches_the_demo_and_the_same_assistant_stays_on_the_page(tmp_path: Path):
    pytest.importorskip("llama_index")
    case = _case()
    example = _example()
    task, question, page = case.read_fixtures()
    assert task == example.TASK
    assert question == example.QUESTION
    assert page == example.PAGE
    assistant = FakeLlm([case.PAGE_DOCUMENT, case.CONTINUATION])
    result, payload = case.run_cookbook(
        named=True,
        assistant=assistant,
        make_checker=_checker,
        sandbox=tmp_path,
    )
    note = next(event.payload for event in result.first.events if event.type == "floor.consult")
    assert result.package == example.receiver_input(example.TASK, note, "checker", "named consult")
    assert f"result retrieve_page: {page}" in result.package
    assert payload["first_answer"] is None
    assert payload["resumed"] == case.CONTINUED
    assert "any time" not in payload["resumed"]
    assert assistant.request_index == 2
    assert (tmp_path / "page-package.txt").read_text(encoding="utf-8") == result.package


def test_unnamed_assistant_can_answer_beyond_the_page(tmp_path: Path):
    pytest.importorskip("llama_index")
    case = _case()
    assistant = FakeLlm([case.PAGE_DOCUMENT])
    result, payload = case.run_cookbook(
        named=False,
        assistant=assistant,
        make_checker=_checker,
        sandbox=tmp_path,
    )
    assert result.resumed is None
    assert payload["first_answer"] == case.BAD


def test_case_owns_the_route_and_does_not_import_the_demo():
    run_text = (CASE / "run.py").read_text(encoding="utf-8")
    graph_text = (CASE / "graph.py").read_text(encoding="utf-8")
    example = (REPO / "examples" / "llamaindex_page_consult.py").read_text(encoding="utf-8")
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert "examples/" not in run_text
    assert "examples/" not in graph_text
    assert "VectorStoreIndex" in graph_text
    assert "as_chat_engine" not in graph_text
    assert "cases/llamaindex-page/run.py" in example
    assert "llama-index" not in pyproject
    assert "llama_index" not in pyproject
