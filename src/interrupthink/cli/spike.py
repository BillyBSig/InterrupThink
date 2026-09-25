from __future__ import annotations

import argparse
from pathlib import Path

from interrupthink.eval.g1 import G1_HAPPY_USER_PROMPT, run_path
from interrupthink.eval.osaka_trap import OSAKA_INTERRUPT_B_PROMPT
from interrupthink.providers.live import LiveLlm, load_dotenv
from interrupthink.runtime.log import JsonlLogger


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="G1 spike paths")
    parser.add_argument("path", choices=("happy", "interrupt", "tool"))
    parser.add_argument(
        "--log",
        default="plan/experiments/runs/spike.jsonl",
        help="JSONL output path",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="B = gpt-5.6-luna effort=none (happy|interrupt)",
    )
    args = parser.parse_args(argv)
    if args.live and args.path == "tool":
        parser.error("--live tool gate is out of scope (dummy tool only)")
    logger = JsonlLogger(Path(args.log))
    llm = None
    if args.live:
        load_dotenv()
        prompt = G1_HAPPY_USER_PROMPT if args.path == "happy" else OSAKA_INTERRUPT_B_PROMPT
        llm = LiveLlm(user_prompt=prompt)
    result = run_path(args.path, logger=logger, llm=llm)
    print(
        f"{result.path} requests={result.request_count} "
        f"interrupts={len(result.interrupt_ids)} "
        f"dropped={result.dropped_ids} "
        f"answer={result.committed_answer!r}"
    )
    print(f"log={args.log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
