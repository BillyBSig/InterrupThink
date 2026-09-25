from pathlib import Path

import pytest

from src.parse.steps import parse_steps
from src.providers.fake import FakeLlm
from src.runtime.log import JsonlLogger
from src.eval.g1 import INTERRUPT_XML_1, INTERRUPT_XML_2, run_path


@pytest.mark.parametrize("n", [1, 2])
def test_happy_path_commits_without_interrupt(n, tmp_path: Path):
    result = run_path("happy", logger=JsonlLogger(tmp_path / f"happy-{n}.jsonl"))
    assert result.request_count == 1
    assert result.interrupt_ids == []
    assert result.dropped_ids == []
    assert result.committed_answer
    assert any(r["event"] == "answer.commit" for r in result.log_records)
    assert any(r["event"] == "thought.unit" for r in result.log_records)


@pytest.mark.parametrize("n", [1, 2])
def test_interrupt_path_drops_tail_and_resumes_clean(n, tmp_path: Path):
    result = run_path("interrupt", logger=JsonlLogger(tmp_path / f"interrupt-{n}.jsonl"))
    assert result.request_count == 2
    assert len(result.interrupt_ids) == 1
    assert "tu_02" in result.dropped_ids
    assert "Q3 Japan" not in result.prefix
    assert "year is a boom" not in result.prefix
    assert "tail must be dropped" not in result.prefix
    assert "outline the FY revenue claim" in result.prefix
    assert result.committed_answer == "Do not treat Q3 Japan as the annual trend."
    assert any(r["event"] == "floor.interrupt" for r in result.log_records)
    assert any(r["event"] == "floor.resume" for r in result.log_records)
    unit_ids = [r["unit_id"] for r in result.log_records if r["event"] == "thought.unit"]
    assert unit_ids == ["tu_01", "tu_02", "tu_03"]


def test_interrupt_restart_mode_clears_prefix(tmp_path: Path):
    llm = FakeLlm([INTERRUPT_XML_1, INTERRUPT_XML_2])
    llm.resume_mode = "restart"
    llm.trial_seed = "s0"
    llm.user_prompt = "start"
    llm.prefix = "OLD PREFIX WITH Q3 Japan"
    result = run_path("interrupt", llm=llm, logger=JsonlLogger(tmp_path / "restart.jsonl"))
    resume = next(r for r in result.log_records if r["event"] == "floor.resume")
    assert resume["mode"] == "restart"
    assert resume["prefix"] == ""
    assert llm.prefix is None
    assert "NEW analysis from scratch" in llm.user_prompt
    assert result.committed_answer == "Do not treat Q3 Japan as the annual trend."


@pytest.mark.parametrize("n", [1, 2])
def test_tool_path_waits_for_ok(n, tmp_path: Path):
    result = run_path("tool", logger=JsonlLogger(tmp_path / f"tool-{n}.jsonl"))
    events = [r["event"] for r in result.log_records]
    assert "tool.gate.release" in events
    assert "tool.execute" in events
    assert events.index("tool.gate.release") < events.index("tool.execute")
    assert result.tool_calls == [{"name": "fetch_baseline", "args": {"window": "FY"}}]
    assert result.interrupt_ids == []
    assert result.committed_answer == "Baseline is ready."


def test_plain_sentence_is_one_claim():
    doc = parse_steps("just prose, no steps")
    assert doc.units[0].kind == "claim"
    assert doc.units[0].text == "just prose, no steps"
