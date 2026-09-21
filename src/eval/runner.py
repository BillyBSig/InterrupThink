from __future__ import annotations

import time
from typing import Protocol

from src.eval.metrics import score_p1, score_p2, score_p3
from src.eval.scenario import C0_PASS1_XML, C0_PASS2_XML, C1_PASS1_XML, C1_PASS2_XML, STUB_CRITIQUE
from src.eval.types import TrialResult
from src.eval.osaka_trap import osaka_monitor, stub_supervisor_ask
from src.monitor.llm import LlmMonitor
from src.monitor.scripted import ScriptedMonitor
from src.providers.fake import FakeLlm
from src.runtime.log import JsonlLogger
from src.eval.g1 import run_path


class Critic(Protocol):
    def critique(self, answer: str) -> str: ...


class StubCritic:
    """Slice 1 stand-in for A. Live LlmMonitor is T2.1 slice 2."""

    def critique(self, answer: str) -> str:
        return STUB_CRITIQUE


def run_c0(
    *,
    seed: str = "stub-0",
    llm: FakeLlm | None = None,
    critic: Critic | None = None,
    logger: JsonlLogger | None = None,
) -> TrialResult:
    """C0 stub: B finishes → A critiques final answer only → B restarts once."""
    logger = logger or JsonlLogger()
    llm = llm or FakeLlm([C0_PASS1_XML, C0_PASS2_XML])
    critic = critic or StubCritic()
    monitor = ScriptedMonitor(trigger_kind=None)
    t0 = time.monotonic()
    first = run_path("happy", llm=llm, monitor=monitor, logger=logger)
    if not first.committed_answer:
        raise RuntimeError("C0 pass 1 produced no <answer>")
    critique = critic.critique(first.committed_answer)
    p4_s = time.monotonic() - t0
    second = run_path("happy", llm=llm, monitor=monitor, logger=logger)
    tokens_b = llm.tokens_emitted
    tokens_a = max(1, len(critique.split()))
    return TrialResult(
        condition="C0",
        seed=seed,
        final_answer=second.committed_answer,
        p1=score_p1(second.committed_answer),
        p2=score_p2(condition="C0", interrupt_before_answer=False, rejects_q3_trend=False),
        p3=score_p3(tokens_b=tokens_b, tokens_a=tokens_a, tokens_wasted=llm.tokens_wasted),
        p4_s=p4_s,
        false_interrupts=0,
        interrupts_used=0,
        critique=critique,
        notes=["stub C0; not a live G2 trial"],
    )


def run_c1(
    *,
    seed: str = "stub-0",
    llm: FakeLlm | None = None,
    monitor: LlmMonitor | None = None,
    logger: JsonlLogger | None = None,
) -> TrialResult:
    """C1: G1 floor + on-demand A (budget 2). Stub ask by default; not a live G2 trial."""
    logger = logger or JsonlLogger()
    llm = llm or FakeLlm([C1_PASS1_XML, C1_PASS2_XML])
    monitor = monitor or osaka_monitor(ask=stub_supervisor_ask, budget=2)
    t0 = time.monotonic()
    result = run_path("interrupt", llm=llm, monitor=monitor, logger=logger)
    p4_s = (monitor.t_first_false - t0) if monitor.t_first_false is not None else (time.monotonic() - t0)
    interrupt_before_answer = bool(result.interrupt_ids)
    return TrialResult(
        condition="C1",
        seed=seed,
        final_answer=result.committed_answer,
        p1=score_p1(result.committed_answer),
        p2=score_p2(
            condition="C1",
            interrupt_before_answer=interrupt_before_answer,
            rejects_q3_trend=monitor.last_rejects_q3,
        ),
        p3=score_p3(
            tokens_b=llm.tokens_emitted,
            tokens_a=monitor.tokens_a or monitor.calls,
            tokens_wasted=llm.tokens_wasted,
        ),
        p4_s=max(0.0, p4_s),
        false_interrupts=monitor.false_interrupt_count,
        interrupts_used=monitor.interrupts_used,
        critique=monitor.last_diagnosis,
        notes=["stub C1; not a live G2 trial"],
    )
