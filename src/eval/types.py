from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TrialResult:
    condition: str
    seed: str
    final_answer: str | None
    p1: int
    p2: int
    p3: int
    p4_s: float
    false_interrupts: int = 0
    interrupts_used: int = 0
    critique: str | None = None
    notes: list[str] = field(default_factory=list)
