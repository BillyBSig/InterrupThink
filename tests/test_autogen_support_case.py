"""The support cookbook hands the same package to a human and starts no second agent."""

import importlib.util
import sys
from pathlib import Path

import pytest

from interrupthink import FakeLlm

REPO = Path(__file__).resolve().parents[1]
CASE = REPO / "cases" / "autogen-support"


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
    return _load(CASE / "run.py", "autogen_support_case_run")


def _example():
    return _load(REPO / "examples" / "autogen_support_takeover.py", "autogen_support_takeover_case_check")


def test_fixture_matches_the_demo_and_the_human_receives_it(tmp_path: Path):
    pytest.importorskip("autogen")
    case = _case()
    example = _example()
    task, held = case.read_fixtures()
    assert task == example.TASK
    assert held == example.HOLD_RESULT
    agent = FakeLlm([case.SUPPORT_DOCUMENT])
    result, payload = case.run_cookbook(named=True, agent_llm=agent, sandbox=tmp_path)
    note = next(event.payload for event in result.first.events if event.type == "floor.takeover")
    assert result.package == example.receiver_input(example.TASK, note, "human", "named owner")
    assert f"result hold_reply: {held}" in result.package
    assert payload["agents"] == ["support"]
    assert payload["first_answer"] is None
    assert agent.resume_envelope == ""
    assert (tmp_path / "human-package.txt").read_text(encoding="utf-8") == result.package


def test_unnamed_agent_can_commit_the_off_task_reply(tmp_path: Path):
    pytest.importorskip("autogen")
    case = _case()
    agent = FakeLlm([case.SUPPORT_DOCUMENT])
    result, payload = case.run_cookbook(named=False, agent_llm=agent, sandbox=tmp_path)
    assert result.package == ""
    assert payload["first_answer"] == case.OFF_TASK
    assert payload["agents"] == ["support"]


def test_case_owns_the_route_and_does_not_import_the_demo():
    run_text = (CASE / "run.py").read_text(encoding="utf-8")
    graph_text = (CASE / "graph.py").read_text(encoding="utf-8")
    example = (REPO / "examples" / "autogen_support_takeover.py").read_text(encoding="utf-8")
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert "examples/" not in run_text
    assert "examples/" not in graph_text
    assert graph_text.count("ConversableAgent(") == 1
    assert "initiate_chat" not in graph_text
    assert "cases/autogen-support/run.py" in example
    assert "autogen" not in pyproject
