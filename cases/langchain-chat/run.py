"""LangChain chat: check a claim before publishing an answer.

Scenario
    Two conversational turns with ``MessagesPlaceholder`` answer a
    device-limit question. The public help text is stale, while the supervisor
    knows that multiple devices are allowed.

Flow
    Each turn is ``run_turn`` → ``run_session`` in ``chat.py``; chat history
    carries across turns. ``LlmMonitor`` checks a claim before publication.

Expected
    On a false-claim turn: non-empty ``interrupt_ids``; committed answer does not repeat
    the one-device policy. Two-turn analysis under ``runs/last-live/``.

Usage (repo root)::

    pip install langchain          # venv only; do not uv-add
    python3 cases/langchain-chat/run.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from interrupthink import load_dotenv


_CASE = Path(__file__).resolve().parent
if str(_CASE) not in sys.path:
    sys.path.insert(0, str(_CASE))

from chat import run_chat  # noqa: E402
from config import DEFAULT_SANDBOX, RUNS  # noqa: E402

run_chat = run_chat


def dump_analysis(label: str, payload: dict, *, out_dir: Path | None = None) -> Path:
    dest_dir = out_dir or (RUNS / "last-live")
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{label}.json"
    body = {
        "label": label,
        "at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _print(label: str, payload: dict, path: Path) -> None:
    print(f"== {label} ==")
    print("answers", payload["committed_answers"])
    print("interrupt_ids", payload["interrupt_ids"])
    print("false_policy_in_history", payload["false_policy_in_history"])
    print("reply_text", payload["reply_text"])
    print("analysis_json", path)


def _has_live_key() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LangChain chat cookbook")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args(argv)

    load_dotenv()
    if not _has_live_key():
        print("skip live: no OPENAI_API_KEY / LLM_API_KEY")
        return 0
    out = RUNS / "last-live"
    live_root = args.root if args.root is not None else DEFAULT_SANDBOX / "live"
    payload = run_chat(interrupt=True, sandbox=live_root)
    path = dump_analysis("live_chat", payload, out_dir=out)
    _print("live_chat", payload, path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
