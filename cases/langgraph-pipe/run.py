"""LangGraph: pass reviewed information between two nodes.

Scenario
    One node retrieves a refund-policy fixture; a second node would write
    ``decision.txt``. A stale 2019 claim must not become a sandbox decision.

Flow
    ``StateGraph``: START → retrieve (``run_session``) → write (``run_session``) or END.
    The host forwards the reviewed text into the second node. The graph keeps
    the handoff one-way and uses one ``LlmMonitor``.

Expected
    Stale retrieve: write node is not visited; no ``decision.txt``; one session.
    Current policy: two sessions, one decision file. Analysis under ``runs/``.

Usage (repo root; local venv)::

    pip install langgraph    # do not uv-add
    python3 cases/langgraph-pipe/run.py   # personal .env keys
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.providers.live import load_dotenv

_CASE = Path(__file__).resolve().parent
if str(_CASE) not in sys.path:
    sys.path.insert(0, str(_CASE))

from config import DEFAULT_SANDBOX, RETRIEVE_CURRENT, RETRIEVE_STALE, RETRIEVE_STOPPED, RUNS  # noqa: E402
from graph import analyze, run_langgraph_pipe, _write_xml  # noqa: E402

analyze = analyze
run_langgraph_pipe = run_langgraph_pipe
_write_xml = _write_xml
RETRIEVE_STALE = RETRIEVE_STALE
RETRIEVE_STOPPED = RETRIEVE_STOPPED
RETRIEVE_CURRENT = RETRIEVE_CURRENT


def _has_live_key() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY"))


def dump_analysis(label: str, payload: dict, *, out_dir: Path | None = None) -> Path:
    dest = out_dir or (RUNS / "last-fake")
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{label}.json"
    body = {"label": label, "at": datetime.now(timezone.utc).isoformat(), **payload}
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _print(label: str, payload: dict, path: Path) -> None:
    print(f"== {label} ==")
    for key in (
        "session_count",
        "interrupt_ids",
        "retrieve_calls",
        "write_calls",
        "decision_exists",
        "write_node_visits",
        "forwarded",
    ):
        print(key, payload.get(key))
    print("analysis_json", path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LangGraph two-node handoff")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args(argv)
    load_dotenv()
    if not _has_live_key():
        print("skip live: no OPENAI_API_KEY / LLM_API_KEY")
        return 0
    blocked = run_langgraph_pipe(
        interrupt_stale=True,
        sandbox=(args.root / "interrupt") if args.root else DEFAULT_SANDBOX / "live-interrupt",
    )
    a1 = analyze(blocked)
    p1 = dump_analysis("live_stale_interrupt", a1, out_dir=RUNS / "last-live")
    _print("live_stale_interrupt", a1, p1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
