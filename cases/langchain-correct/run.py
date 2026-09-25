"""LangChain: correct a wrong host claim, then continue.

Scenario
    A specialist behind a LangChain wrapper (prompt template + ``Runnable``)
    works on a deployment ticket. The ticket says production, while the
    supervisor knows the target is staging. After correction, the session
    continues and may write staging.txt.

Flow
    ``create_specialist`` / ``.run()`` in ``agents.py``; the live model is
    ``LiveLlm``. The correction is carried into the resumed request.

Expected
    With interrupt: no ``production.txt``, ``staging.txt`` exists, ``resume_modes`` are
    rollback. Without interrupt (tests): ``production.txt`` is written.
    Requires a personal API key in ``.env`` (exits cleanly if missing).

Usage (repo root)::

    pip install langchain          # venv only; do not uv-add
    python3 cases/langchain-correct/run.py
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

from agents import analyze, create_specialist  # noqa: E402
from config import DEFAULT_SANDBOX, RUNS  # noqa: E402

create_specialist = create_specialist
analyze = analyze


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
    print("answer", payload["committed_answer"])
    print("interrupt_ids", payload["interrupt_ids"])
    print("request_count", payload["request_count"])
    print("resume_modes", payload["resume_modes"])
    print("written", payload["written"])
    print("production_exists", payload["production_exists"])
    print("staging_exists", payload["staging_exists"])
    print("lc_tool_name", payload["lc_tool_name"])
    print("analysis_json", path)


def _has_live_key() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LangChain correct-then-continue")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args(argv)

    load_dotenv()
    if not _has_live_key():
        print("skip live: no OPENAI_API_KEY / LLM_API_KEY")
        return 0
    out = RUNS / "last-live"
    live_root = args.root if args.root is not None else DEFAULT_SANDBOX / "live"
    specialist = create_specialist(interrupt=True, sandbox=live_root)
    payload = analyze(specialist.run())
    path = dump_analysis("live_interrupt", payload, out_dir=out)
    _print("live_interrupt", payload, path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
