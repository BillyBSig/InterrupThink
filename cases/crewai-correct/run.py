"""CrewAI: correct a wrong host claim, then continue.

Scenario
    One CrewAI role (Agent + Task, Process.sequential) works on a deployment
    ticket. The ticket says production, while the supervisor knows the target
    is staging. After the correction, the session rolls back and may write
    staging.txt.

Flow
    The host calls ``run_session`` inside the role's work. CrewAI manages the
    role and task configuration.

Expected
    With interrupt: no ``production.txt``; ``staging.txt`` exists; resume ``rollback``.
    Without interrupt (tests): ``production.txt`` is written.
    Requires a personal API key in ``.env`` (exits cleanly if missing).

Usage (repo root; local venv)::

    pip install crewai    # do not uv-add
    python3 cases/crewai-correct/run.py
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
from graph import analyze, run_crewai_correct  # noqa: E402

analyze = analyze
run_crewai_correct = run_crewai_correct


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
        "request_count",
        "resume_modes",
        "written",
        "production_exists",
        "staging_exists",
        "agent_count",
        "committed_answer",
    ):
        print(key, payload.get(key))
    print("analysis_json", path)


def _has_live_key() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CrewAI correct-then-continue")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args(argv)

    load_dotenv()
    if not _has_live_key():
        print("skip live: no OPENAI_API_KEY / LLM_API_KEY")
        return 0
    out = RUNS / "last-live"
    live_root = args.root if args.root is not None else DEFAULT_SANDBOX / "live"
    payload = analyze(run_crewai_correct(interrupt=True, sandbox=live_root))
    path = dump_analysis("live_interrupt", payload, out_dir=out)
    _print("live_interrupt", payload, path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
