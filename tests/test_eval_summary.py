from src.eval.scenario import (
    A_MEMO,
    STUB_CRITIQUE,
    interrupt_restart_prompt,
    restart_prompt,
    resume_llm_prompt,
    llm_prompt,
)
from src.eval.summary import evaluate_gates
from src.eval.types import TrialResult


def _trial(condition: str, p1: int, p2: int, p3: int, p4: float, fi: int = 0) -> TrialResult:
    return TrialResult(condition, "s0", "ans", p1, p2, p3, p4, false_interrupts=fi)


def test_llm_prompt_hides_memo():
    text = llm_prompt("s0")
    assert "Q3" in text
    assert "+42" in text
    assert "hanya supervisor" not in text
    assert "FY rolling 12 bulan" not in text
    assert "-4%" not in text
    assert "6 minggu" not in text
    assert A_MEMO not in text


def test_llm_prompt_require_draft_does_not_leak_memo():
    text = llm_prompt("s0", require_draft=True)
    assert "answer_draft" in text
    assert "recommendation you are about to commit" in text
    assert A_MEMO not in text
    assert "-4%" not in text


def test_restart_prompt_allows_supervisor_critique():
    text = restart_prompt("s0", STUB_CRITIQUE)
    assert "FY rolling" in text
    assert "-4%" in text
    assert "You MAY use figures and policy stated in the critique" in text
    assert "hanya supervisor" not in text
    assert "Use only the public data above" not in text


def test_resume_llm_prompt_is_binding_not_stacked():
    text = resume_llm_prompt("s0", "FY rolling 12-month Osaka volume is -4%")
    assert "FY rolling 12-month Osaka volume is -4%" in text
    assert "Do not use Q3 +42% as the demand basis" in text
    assert "Use only the public data above" not in text
    assert "Volume pengiriman Osaka Q3" not in text
    assert A_MEMO not in text


def test_interrupt_restart_prompt_is_from_scratch_with_emphasis():
    text = interrupt_restart_prompt("s0", "FY rolling 12-month Osaka volume is -4%")
    assert "NEW analysis from scratch" in text
    assert "Previous demand reasoning was WRONG" in text
    assert "FY rolling 12-month Osaka volume is -4%" in text
    assert "continuing from the prefix" not in text
    assert "Volume pengiriman Osaka Q3" not in text
    assert A_MEMO not in text


def test_evaluate_gates_meet_and_miss():
    win = [
        (_trial("C0", 0, 0, 100, 10), _trial("C1", 1, 1, 80, 3))
        for _ in range(8)
    ]
    gates = evaluate_gates(win)
    assert gates["n"] == 8
    assert gates["meets_go_threshold"] is True
    assert gates["proposal"] == "Go"
    lose = [
        (_trial("C0", 1, 0, 50, 5), _trial("C1", 0, 0, 200, 20, fi=1))
        for _ in range(8)
    ]
    assert evaluate_gates(lose)["meets_go_threshold"] is False
    assert evaluate_gates(lose)["proposal"] == "Kill"


def test_evaluate_gates_p1_primary_does_not_veto_on_fi():
    pairs = [
        (_trial("C0", 1, 0, 100, 10), _trial("C1", 1, 1, 80, 3, fi=1))
        for _ in range(8)
    ]
    gates = evaluate_gates(pairs)
    assert gates["p1_ok"] is True
    assert gates["fi_ok"] is False
    assert gates["meets_go_threshold"] is True
    assert gates["proposal"] == "Go"
    assert gates["wasit"] == "p1_primary"


def test_evaluate_gates_hold_on_errors():
    err = TrialResult("C0", "s0", None, 0, 0, 0, 0.0, notes=["error: boom"])
    other = TrialResult("C1", "s0", None, 0, 0, 0, 0.0, notes=["error: boom"])
    gates = evaluate_gates([(err, other)])
    assert gates["proposal"] == "Hold"
    assert gates["meets_go_threshold"] is False
