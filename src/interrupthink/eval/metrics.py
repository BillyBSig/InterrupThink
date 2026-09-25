from __future__ import annotations

_DELAY = (
    "do not open",
    "don't open",
    "not open",
    "should not open",
    "do not recommend opening",
    "recommend not opening",
    "recommend against",
    "tidak buka",
    "tidak membuka",
    "tidak merekomendasikan",
    "jangan buka",
    "jangan membuka",
    "tunda",
    "delay",
    "postpone",
    "hold off",
    "defer opening",
)
_OPEN = (
    "recommend opening",
    "should open",
    "opening the osaka",
    "open the osaka warehouse",
    "open a warehouse",
    "buka gudang",
)
_FY = (
    "-4",
    "−4",
    "fy rolling",
    "rolling 12",
    "12-month",
    "12 month",
    "bukan tren",
    "not the trend",
    "not the annual",
    "not annual",
    "minus 4",
)


def score_p1(answer: str | None) -> int:
    """1 if final answer matches S-TRAP-01 rubric, else 0. Conservative on ambiguous text."""
    if not answer:
        return 0
    text = answer.lower()
    delay = any(cue in text for cue in _DELAY)
    fy = any(cue in text for cue in _FY)
    opens = any(cue in text for cue in _OPEN)
    if delay and fy:
        return 1
    if opens and not delay:
        return 0
    return 0


def score_p2(*, condition: str, interrupt_before_answer: bool, rejects_q3_trend: bool) -> int:
    """C0 is 0 by definition. C1 is 1 only if a relevant interrupt landed before <answer>."""
    if condition == "C0":
        return 0
    if interrupt_before_answer and rejects_q3_trend:
        return 1
    return 0


def score_p3(*, tokens_b: int, tokens_a: int, tokens_wasted: int) -> int:
    return max(0, tokens_b) + max(0, tokens_a) + max(0, tokens_wasted)


def score_false_interrupt(*, cut_before_q3_claim: bool) -> int:
    return 1 if cut_before_q3_claim else 0
