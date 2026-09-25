from __future__ import annotations

import argparse
from pathlib import Path

from interrupthink.eval.live import run_paired_trials, run_stub_pairs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Eval S-TRAP-01: C0 vs C1 or G3 ablation")
    parser.add_argument("--pairs", type=int, default=8)
    parser.add_argument("--stub", action="store_true", help="FakeLlm + stub A (not wasit)")
    parser.add_argument(
        "--ablation",
        choices=["a31", "a32", "a33", "a34"],
        default=None,
        help="G3: a31 filter; a32 draft gate; a33 restart; a34 observe-only",
    )
    parser.add_argument(
        "--out",
        default="plan/experiments/runs/g2-01",
        help="directory for JSONL + summary.json",
    )
    args = parser.parse_args(argv)
    if args.stub:
        payload = run_stub_pairs(args.pairs)
        print(payload["gates"])
        return 0
    payload = run_paired_trials(args.pairs, Path(args.out), ablation=args.ablation)
    gates = payload["gates"]
    print(
        f"n={gates['n']} P1 base={gates['p1_c0']:.2f} treat={gates['p1_c1']:.2f} "
        f"P2={gates['p2_c1']:.2f} P3 base={gates['p3_c0']:.0f} treat={gates['p3_c1']:.0f} "
        f"P4 base={gates['p4_c0_s']:.1f}s treat={gates['p4_c1_s']:.1f}s "
        f"FI={gates['false_interrupt_mean']:.2f} "
        f"meets_go_threshold={gates['meets_go_threshold']} "
        f"proposal={gates.get('proposal')}"
    )
    print(f"out={args.out}")
    print("Not a gate lock. Human sign-off required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
