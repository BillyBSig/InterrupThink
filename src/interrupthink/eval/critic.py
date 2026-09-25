from __future__ import annotations

import os

from interrupthink.eval.scenario import A_MEMO
from interrupthink.monitor.llm import complete_text

_CRITIC_INSTRUCTIONS = """You are supervisor A. You see ONLY B's final answer, not B's steps.
You have an internal memo B does not have.
If B used Q3 +42% as the annual demand trend, say that is wrong and cite FY rolling -4% and FY policy.
Write a short critique B can use to redo the analysis from scratch.
Do not claim you watched B's reasoning stream."""


class LiveCritic:
    """C0 A: final-answer only. Not used on C1's streaming path."""

    def __init__(self) -> None:
        self.tokens_a = 0
        self.model = os.environ.get("SUPERVISOR_MODEL", "gpt-5.6-luna")
        self.effort = os.environ.get("SUPERVISOR_REASONING_EFFORT", "medium")
        self.api_key = os.environ.get("SUPERVISOR_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self.base_url = (
            os.environ.get("SUPERVISOR_BASE_URL") or "https://api.openai.com/v1"
        ).rstrip("/")

    def critique(self, answer: str) -> str:
        text = complete_text(
            model=self.model,
            effort=self.effort,
            api_key=self.api_key or "",
            base_url=self.base_url,
            instructions=_CRITIC_INSTRUCTIONS,
            user=f"{A_MEMO}\n\nB final answer:\n{answer}",
        )
        self.tokens_a += max(1, len(text.split()))
        return text
