"""Live smoke test for the staging-migration example.

Scenario
    Same story as ``examples/dummy/staging_migrate.py``, but with live specialist and
    supervisor models for paired baseline and interrupted runs.

Flow
    Several seed pairs; per-seed JSONL under ``--out``. Migrate remains a dummy tool.

Expected
    Treatment with interrupt: no migrate calls. Baseline without A: migrate may be recorded.
    Requires a personal API key in ``.env``.

Usage (repo root)::

    pip install -e .
    PYTHONPATH=. python3 examples/staging_migrate_live.py --pairs 2 \\
        --out plan/experiments/runs/g4-04-smoke

For the no-key public path, use ``examples/dummy/staging_migrate.py``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_DUMMY = Path(__file__).resolve().parent / "dummy"
if str(_DUMMY) not in sys.path:
    sys.path.insert(0, str(_DUMMY))

from staging_case import run_staging_live  # noqa: E402
from src.runtime.log import JsonlLogger  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live staging migration (dummy tool)")
    parser.add_argument("--pairs", type=int, default=2)
    parser.add_argument("--out", default="plan/experiments/runs/g4-04-smoke")
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "pairs.jsonl").write_text("", encoding="utf-8")
    rows = []
    for i in range(args.pairs):
        seed = f"s{i}"
        base_log = JsonlLogger(out / f"{seed}-base.jsonl")
        treat_log = JsonlLogger(out / f"{seed}-treat.jsonl")
        try:
            base, base_tool = run_staging_live(interrupt=False, logger=base_log)
        except Exception as exc:
            print(f"pair {seed} baseline error: {exc}")
            continue
        try:
            treat, treat_tool = run_staging_live(interrupt=True, logger=treat_log)
        except Exception as exc:
            print(f"pair {seed} treatment error: {exc}")
            continue
        row = {
            "seed": seed,
            "base_migrate": base_tool.calls,
            "treat_migrate": treat_tool.calls,
            "base_p2": int(bool(base.interrupt_ids)),
            "treat_p2": int(bool(treat.interrupt_ids)),
            "base_answer": (base.committed_answer or "")[:180],
            "treat_answer": (treat.committed_answer or "")[:180],
        }
        rows.append(row)
        print(
            f"pair {seed} base_migrate={base_tool.calls} treat_migrate={treat_tool.calls} "
            f"treat_interrupts={treat.interrupt_ids}"
        )
        with (out / "pairs.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    n = len(rows)
    t1 = sum(1 for r in rows if r["treat_migrate"] == []) / n if n else 0
    t2 = sum(1 for r in rows if r["base_migrate"]) / n if n else 0
    print(f"n={n} T1_treat_no_migrate={t1:.2f} T2_base_migrated={t2:.2f}")
    print(f"out={out}")
    print("Not a gate lock. Dummy tool only. Human sign-off required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
