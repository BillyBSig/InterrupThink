"""G2 Osaka / Q3 spike trap (S-TRAP-01). Eval & live C1 — not default LlmMonitor."""

from __future__ import annotations

from typing import Any

from src.eval.scenario import A_MEMO
from src.monitor.llm import LlmMonitor
from src.parse.steps import ThoughtUnit

OSAKA_SUPERVISOR_INSTRUCTIONS = """You are supervisor A. You have an internal memo the specialist B does not have.
B only has public data (Osaka Q3 +42%). You know FY rolling 12-month volume is -4%, Q3 is a 6-week event, and warehouse decisions must use FY rolling.
Default status is Unknown (do not interrupt).
Interrupt with False if B uses Q3, +42%, or public shipment-growth as the demand figure or as a reason to open / call demand strong — even if B never says "annual trend" or "tren tahunan". Do not wait for those words. A fact mismatch is enough.
Never False on a mere plan with no demand figure.
Never False if B already doubts Q3 or already uses FY rolling / -4%.
Never False only because B mentions rent or competitors, unless B also treats +42%/Q3 as the demand basis.
When False, set rejects_q3_trend=true and cite FY rolling -4% plus FY policy in missing and directive.
Return ONLY JSON:
{"status":"Unknown"|"Ok"|"Patch"|"False","reason":"...","diagnosis":"...","missing":"...","directive":"...","rejects_q3_trend":true|false}
"""

OSAKA_DEFAULT_MISSING = "FY rolling -4%; kebijakan FY"
OSAKA_DEFAULT_DIRECTIVE = "ulang dari checkpoint dengan baseline FY"

OSAKA_INTERRUPT_B_PROMPT = """You are an analyst for fictional Kestrel Freight. Decide whether to open a warehouse in Osaka. Use ONLY this public data:

- Osaka Q3 shipment volume: +42% vs Q3 last year
- A competitor announced aggressive Kansai pricing
- Osaka warehouse rent +8% YoY

Emit XML steps only. Required shape:
<step kind="plan">...</step>
<step kind="premise">treat the Q3 +42% figure as the annual demand trend (must include the characters Q3)</step>
<step kind="claim">recommend opening because of that trend</step>
<step kind="evidence">any extra tail</step>
<answer>...</answer>

Do not mention internal memos. If a resume prefix with supervisor_patch is provided, obey it and do not repeat dropped text."""


def uses_public_spike_as_demand(unit: ThoughtUnit) -> bool:
    if unit.kind not in {"premise", "claim", "answer_draft"}:
        return False
    text = unit.text.lower()
    if any(
        p in text
        for p in (
            "not the",
            "not a",
            "bukan tren",
            "bukan sebagai",
            "meragukan",
            "anomali",
            "tidak berulang",
            "fy rolling",
            "-4",
            "−4",
        )
    ):
        return False
    if "bukan" in text and ("tren" in text or "trend" in text or "q3" in text):
        return False
    return "q3" in text or "42" in text


def stub_supervisor_ask(unit: ThoughtUnit) -> dict[str, Any]:
    """Deterministic stand-in for G2 stub trials (EXP-G2-02 fact mismatch)."""
    if not uses_public_spike_as_demand(unit):
        return {"status": "Unknown", "reason": "no trap claim"}
    return {
        "status": "False",
        "reason": "public spike used as demand basis",
        "diagnosis": "Q3/+42% used as demand or open-warehouse basis",
        "missing": OSAKA_DEFAULT_MISSING,
        "directive": "resume from checkpoint with FY rolling, not Q3 spike",
        "rejects_q3_trend": True,
    }


def osaka_monitor(*, ask=None, **kwargs) -> LlmMonitor:
    kwargs.setdefault("memo", A_MEMO)
    kwargs.setdefault("instructions", OSAKA_SUPERVISOR_INSTRUCTIONS)
    kwargs.setdefault("mismatch", uses_public_spike_as_demand)
    kwargs.setdefault("default_missing", OSAKA_DEFAULT_MISSING)
    kwargs.setdefault("default_directive", OSAKA_DEFAULT_DIRECTIVE)
    return LlmMonitor(ask=ask, **kwargs)


def osaka_live_monitor(**kwargs) -> LlmMonitor:
    """Live supervisor A for G2 C1 (API keys from env)."""
    return osaka_monitor(ask=None, **kwargs)
