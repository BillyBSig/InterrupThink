from __future__ import annotations

from src.eval.types import TrialResult


def evaluate_gates(pairs: list[tuple[TrialResult, TrialResult]]) -> dict:
    """G2 thresholds. Go wasit = P1 (ADR-0005). Does not lock the gate."""
    n = len(pairs)
    if n == 0:
        return {"n": 0, "meets_go_threshold": False, "reason": "no pairs"}
    p1_c0 = sum(a.p1 for a, _ in pairs) / n
    p1_c1 = sum(b.p1 for _, b in pairs) / n
    p1_majority = sum(b.p1 >= a.p1 for a, b in pairs) / n
    p2_c1 = sum(b.p2 for _, b in pairs) / n
    p3_c0 = sum(a.p3 for a, _ in pairs) / n
    p3_c1 = sum(b.p3 for _, b in pairs) / n
    p4_c0 = sum(a.p4_s for a, _ in pairs) / n
    p4_c1 = sum(b.p4_s for _, b in pairs) / n
    fi = sum(b.false_interrupts for _, b in pairs) / n
    error_n = sum(
        1
        for a, b in pairs
        if any(str(note).startswith("error:") for note in (a.notes + b.notes))
    )
    p1_ok = p1_majority >= 0.5
    p2_ok = p2_c1 >= 0.6
    p3_ok = p3_c1 <= 1.25 * p3_c0 or (
        p3_c1 > p3_c0 and p4_c0 > 0 and p4_c1 <= 0.5 * p4_c0 and p1_c1 >= p1_c0
    )
    fi_ok = fi < 0.3
    kill_p1 = p1_c1 + 0.05 < p1_c0
    kill_p2 = p2_c1 < 0.3
    kill_p3 = p3_c0 > 0 and p3_c1 > 1.5 * p3_c0 and p1_c1 < p1_c0
    fi_hurts_p1 = fi >= 0.3 and kill_p1
    systematic_error = error_n >= max(1, n / 2)
    # ADR-0005: P1 is the Go wasit. P2/P4/FI are guards.
    meets = p1_ok and not kill_p1 and not systematic_error
    if systematic_error:
        proposal = "Hold"
    elif kill_p1 or fi_hurts_p1 or kill_p3:
        proposal = "Kill"
    elif meets:
        proposal = "Go"
    elif p1_ok and not p2_ok and abs(p1_c1 - p1_c0) <= 0.15:
        proposal = "Recycle"
    else:
        proposal = "Hold"
    return {
        "n": n,
        "p1_c0": p1_c0,
        "p1_c1": p1_c1,
        "p1_majority_c1_ge_c0": p1_majority,
        "p2_c1": p2_c1,
        "p3_c0": p3_c0,
        "p3_c1": p3_c1,
        "p4_c0_s": p4_c0,
        "p4_c1_s": p4_c1,
        "false_interrupt_mean": fi,
        "p1_ok": p1_ok,
        "p2_ok": p2_ok,
        "p3_ok": p3_ok,
        "fi_ok": fi_ok,
        "error_n": error_n,
        "meets_go_threshold": meets,
        "proposal": proposal,
        "proposal_note": "usul saja; gerbang tidak terkunci tanpa sign-off manusia; wasit = P1 (ADR-0005)",
        "kill_signals": {
            "p1_worse": kill_p1,
            "p2_low": kill_p2,
            "p3_blow": kill_p3,
            "fi_hurts_p1": fi_hurts_p1,
        },
        "wasit": "p1_primary",
    }
