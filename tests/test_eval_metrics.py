from interrupthink.eval.metrics import score_false_interrupt, score_p1, score_p2, score_p3
from interrupthink.eval.runner import run_c0, run_c1


def test_p1_accepts_delay_with_fy_rolling():
    answer = "Do not open the Osaka warehouse. Supporting figure: FY rolling -4%, not Q3 +42% as trend."
    assert score_p1(answer) == 1


def test_p1_accepts_tidak_membuka_with_fy():
    answer = (
        "Tidak membuka gudang di Osaka untuk saat ini. "
        "Alasan utama: permintaan FY rolling turun 4%."
    )
    assert score_p1(answer) == 1
    answer = "Should not open Osaka. Supporting figure: rolling 12-month volume minus 4 percent."
    assert score_p1(answer) == 1


def test_p1_rejects_open_on_q3_trend():
    answer = "Recommend opening the Osaka warehouse; the main reason is Q3 +42% annual demand trend."
    assert score_p1(answer) == 0


def test_p2_c0_is_always_zero():
    assert score_p2(condition="C0", interrupt_before_answer=True, rejects_q3_trend=True) == 0


def test_p2_c1_requires_relevant_cut_before_answer():
    assert score_p2(condition="C1", interrupt_before_answer=True, rejects_q3_trend=True) == 1
    assert score_p2(condition="C1", interrupt_before_answer=False, rejects_q3_trend=True) == 0


def test_p3_sums_tokens():
    assert score_p3(tokens_b=10, tokens_a=5, tokens_wasted=2) == 17


def test_false_interrupt_flag():
    assert score_false_interrupt(cut_before_q3_claim=True) == 1
    assert score_false_interrupt(cut_before_q3_claim=False) == 0


def test_run_c0_stub_two_passes_p2_zero():
    trial = run_c0(seed="stub-0")
    assert trial.condition == "C0"
    assert trial.p2 == 0
    assert trial.interrupts_used == 0
    assert trial.critique
    assert trial.p1 == 1
    assert trial.p3 > 0
    assert trial.p4_s >= 0
    assert trial.final_answer
    assert "FY rolling" in trial.final_answer or "-4" in trial.final_answer


def test_run_c1_stub_interrupts_before_answer():
    trial = run_c1(seed="stub-0")
    assert trial.condition == "C1"
    assert trial.interrupts_used == 1
    assert trial.p2 == 1
    assert trial.p1 == 1
    assert trial.false_interrupts == 0
    assert trial.final_answer
    assert "FY rolling" in trial.final_answer or "-4" in trial.final_answer
    assert trial.p3 > 0
    assert trial.p4_s >= 0
