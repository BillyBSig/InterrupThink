from __future__ import annotations

import json
import os
import time
from dataclasses import asdict
from pathlib import Path

from src.eval.critic import LiveCritic
from src.eval.metrics import score_p1, score_p2, score_p3
from src.eval.runner import run_c0, run_c1
from src.eval.scenario import restart_prompt, llm_prompt
from src.eval.summary import evaluate_gates
from src.eval.types import TrialResult
from src.eval.osaka_trap import osaka_live_monitor, osaka_monitor, stub_supervisor_ask
from src.monitor.llm import LlmMonitor
from src.monitor.scripted import ScriptedMonitor
from src.providers.live import LiveOpenAILlm, load_dotenv
from src.runtime.log import JsonlLogger
from src.eval.g1 import run_path


def _require_live_key() -> None:
    load_dotenv()
    if not (os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")):
        raise RuntimeError("missing OPENAI_API_KEY / LLM_API_KEY")


def run_c0_live(*, seed: str, logger: JsonlLogger | None = None) -> TrialResult:
    load_dotenv()
    logger = logger or JsonlLogger()
    llm = LiveOpenAILlm(user_prompt=llm_prompt(seed), timeout_s=180.0)
    critic = LiveCritic()
    monitor = ScriptedMonitor(trigger_kind=None)
    t0 = time.monotonic()
    first = run_path("happy", llm=llm, monitor=monitor, logger=logger)
    if not first.committed_answer:
        raise RuntimeError("C0 live pass 1 produced no <answer>")
    critique = critic.critique(first.committed_answer)
    p4_s = time.monotonic() - t0
    llm.user_prompt = restart_prompt(seed, critique)
    llm.prefix = None
    llm.aborted = False
    second = run_path("happy", llm=llm, monitor=monitor, logger=logger)
    return TrialResult(
        condition="C0",
        seed=seed,
        final_answer=second.committed_answer,
        p1=score_p1(second.committed_answer),
        p2=0,
        p3=score_p3(
            tokens_b=llm.tokens_emitted,
            tokens_a=critic.tokens_a,
            tokens_wasted=llm.tokens_wasted,
        ),
        p4_s=p4_s,
        critique=critique,
        notes=["live C0"],
    )


def run_c1_live(
    *,
    seed: str,
    logger: JsonlLogger | None = None,
    monitor: LlmMonitor | None = None,
    condition: str = "C1",
    notes: list[str] | None = None,
    require_draft: bool = False,
    resume_mode: str = "rollback",
) -> TrialResult:
    load_dotenv()
    logger = logger or JsonlLogger()
    llm = LiveOpenAILlm(
        user_prompt=llm_prompt(seed, require_draft=require_draft),
        timeout_s=180.0,
    )
    llm.trial_seed = seed
    llm.resume_mode = resume_mode
    monitor = monitor or osaka_live_monitor()
    t0 = time.monotonic()
    result = run_path("interrupt", llm=llm, monitor=monitor, logger=logger)
    p4_s = (monitor.t_first_false - t0) if monitor.t_first_false is not None else (time.monotonic() - t0)
    return TrialResult(
        condition=condition,
        seed=seed,
        final_answer=result.committed_answer,
        p1=score_p1(result.committed_answer),
        p2=score_p2(
            condition="C1",
            interrupt_before_answer=bool(result.interrupt_ids),
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
        notes=notes or ["live C1"],
    )


def run_a31_filter_live(*, seed: str, logger: JsonlLogger | None = None) -> TrialResult:
    return run_c1_live(
        seed=seed,
        logger=logger,
        monitor=osaka_monitor(ask=stub_supervisor_ask, budget=2),
        condition="A3.1",
        notes=["live A3.1 filter"],
    )


def run_a32_draft_live(*, seed: str, logger: JsonlLogger | None = None) -> TrialResult:
    return run_c1_live(
        seed=seed,
        logger=logger,
        monitor=osaka_live_monitor(askable={"answer_draft"}, budget=2),
        condition="A3.2",
        notes=["live A3.2 answer_draft gate"],
        require_draft=True,
    )


def run_a33_restart_live(*, seed: str, logger: JsonlLogger | None = None) -> TrialResult:
    return run_c1_live(
        seed=seed,
        logger=logger,
        condition="A3.3",
        notes=["live A3.3 full restart"],
        resume_mode="restart",
    )


def run_a34_observe_live(*, seed: str, logger: JsonlLogger | None = None) -> TrialResult:
    return run_c1_live(
        seed=seed,
        logger=logger,
        monitor=LlmMonitor(budget=0),
        condition="A3.4",
        notes=["live A3.4 observe only"],
    )


def _pair_config(ablation: str | None) -> tuple:
    if ablation == "a31":
        return run_c1_live, run_a31_filter_live, "c1", "a31", "C1", "A3.1"
    if ablation == "a32":

        def run_c1_draft(*, seed: str, logger: JsonlLogger | None = None) -> TrialResult:
            return run_c1_live(
                seed=seed,
                logger=logger,
                require_draft=True,
                notes=["live C1 + answer_draft emit"],
            )

        return run_c1_draft, run_a32_draft_live, "c1", "a32", "C1", "A3.2"
    if ablation == "a33":
        return run_c1_live, run_a33_restart_live, "c1", "a33", "C1", "A3.3"
    if ablation == "a34":
        return run_c1_live, run_a34_observe_live, "c1", "a34", "C1", "A3.4"
    return run_c0_live, run_c1_live, "c0", "c1", "C0", "C1"


def run_paired_trials(n: int, out_dir: Path, *, ablation: str | None = None) -> dict:
    _require_live_key()
    out_dir.mkdir(parents=True, exist_ok=True)
    pairs: list[tuple[TrialResult, TrialResult]] = []
    raw_path = out_dir / "pairs.jsonl"
    raw_path.write_text("", encoding="utf-8")
    left_fn, right_fn, left_tag, right_tag, left_cond, right_cond = _pair_config(ablation)
    for i in range(n):
        seed = f"s{i}"
        left_log = JsonlLogger(out_dir / f"{seed}-{left_tag}.jsonl")
        right_log = JsonlLogger(out_dir / f"{seed}-{right_tag}.jsonl")
        try:
            left = left_fn(seed=seed, logger=left_log)
        except Exception as exc:
            left = TrialResult(left_cond, seed, None, 0, 0, 0, 0.0, notes=[f"error: {exc}"])
        try:
            right = right_fn(seed=seed, logger=right_log)
        except Exception as exc:
            right = TrialResult(right_cond, seed, None, 0, 0, 0, 0.0, notes=[f"error: {exc}"])
        pairs.append((left, right))
        with raw_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {"seed": seed, left_tag: asdict(left), right_tag: asdict(right)},
                    ensure_ascii=False,
                )
                + "\n"
            )
        print(
            f"pair {seed} {left.condition} p1={left.p1} p2={left.p2} p3={left.p3} p4={left.p4_s:.1f} "
            f"{right.condition} p1={right.p1} p2={right.p2} p3={right.p3} p4={right.p4_s:.1f} "
            f"fi={right.false_interrupts} notes={left.notes[-1:] + right.notes[-1:]}",
            flush=True,
        )
    gates = evaluate_gates(pairs)
    gates["baseline"] = left_cond
    gates["treatment"] = right_cond
    (out_dir / "summary.json").write_text(json.dumps(gates, indent=2), encoding="utf-8")
    (out_dir / "table.md").write_text(format_run_log(pairs), encoding="utf-8")
    return {"pairs": [(asdict(a), asdict(b)) for a, b in pairs], "gates": gates}


def format_run_log(pairs: list[tuple[TrialResult, TrialResult]]) -> str:
    lines = [
        "| Trial | Kondisi | P1 | P2 | P3 | P4 | FI | Catatan |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for c0, c1 in pairs:
        lines.append(_row(c0))
        lines.append(_row(c1))
    return "\n".join(lines) + "\n"


def _row(trial: TrialResult) -> str:
    note = "; ".join(trial.notes)
    if trial.critique:
        note = (note + " | " + trial.critique[:80]).strip(" |")
    note = note.replace("|", "/")
    return (
        f"| {trial.seed} | {trial.condition} | {trial.p1} | {trial.p2} | "
        f"{trial.p3} | {trial.p4_s:.1f} | {trial.false_interrupts} | {note} |"
    )


def run_stub_pairs(n: int = 2) -> dict:
    pairs = [(run_c0(seed=f"stub-{i}"), run_c1(seed=f"stub-{i}")) for i in range(n)]
    return {"gates": evaluate_gates(pairs), "n": n}
