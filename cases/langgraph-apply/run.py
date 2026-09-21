"""LangGraph integration: replace the agent node and keep ToolNode.

Scenario
    Practitioner already has a 1:1 LangGraph (agent + official ``ToolNode``). Public
    ticket: freeze is over, write hotfix.txt. Supervisor memo: freeze still holds.

Flow
    One hook: the ``agent`` node runs ``run_session`` (ThoughtUnit interrupt). The
    ``tools`` node is ``langgraph.prebuilt.ToolNode``. Graph-level
    ``interrupt_before=["tools"]`` stays theirs as HITL backup — do not decorate ToolNode.

Expected
    With interrupt: ToolNode is not visited, no ``hotfix.txt``.
    Without interrupt: ToolNode writes ``hotfix.txt``. Analysis under ``runs/``.

Usage (repo root; local venv)::

    pip install langgraph langchain    # do not uv-add
    python3 cases/langgraph-apply/run.py
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

from config import DEFAULT_SANDBOX, RUNS  # noqa: E402
from graph import analyze, run_apply  # noqa: E402

analyze = analyze
run_apply = run_apply


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
    for key in (
        "interrupt_ids",
        "tool_node_visits",
        "written",
        "hotfix_exists",
        "committed_answer",
    ):
        print(key, payload.get(key))
    print("analysis_json", path)


def _has_live_key() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LangGraph apply cookbook")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args(argv)

    load_dotenv()
    if not _has_live_key():
        print("skip live: no OPENAI_API_KEY / LLM_API_KEY")
        return 0
    out = RUNS / "last-live"
    live_root = args.root if args.root is not None else DEFAULT_SANDBOX / "live"
    payload = analyze(run_apply(interrupt=True, sandbox=live_root))
    path = dump_analysis("live_interrupt", payload, out_dir=out)
    _print("live_interrupt", payload, path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
