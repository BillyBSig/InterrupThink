"""Run the order crew in this folder, using the transcript fixture."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from interrupthink import ScriptedMonitor

CASE_DIR = Path(__file__).resolve().parent
REPO = CASE_DIR.parents[1]
if str(CASE_DIR) not in sys.path:
    sys.path.insert(0, str(CASE_DIR))

from config import BAD, DEFAULT_SANDBOX, FIXTURES, ORDER_DOCUMENT, RUNS  # noqa: E402
from graph import OrderDesk, run_live_order, run_order_crew  # noqa: E402


def read_fixtures() -> tuple[str, str, str]:
    task = (FIXTURES / "task.txt").read_text(encoding="utf-8").strip()
    transcript = (FIXTURES / "transcript.txt").read_text(encoding="utf-8").strip()
    menu = (FIXTURES / "menu.txt").read_text(encoding="utf-8").strip()
    return task, transcript, menu


def analyze(result, sandbox: Path) -> dict:
    package_path = sandbox / "order-package.txt"
    first = result.first
    return {
        "escalate_to": "" if first is None else first.escalate_to,
        "counter_ran": result.counter_ran,
        "first_answer": None if first is None else first.committed_answer,
        "package": result.package,
        "package_path": str(package_path),
    }


def run_cookbook(*, named: bool, taker_llm, make_counter, sandbox: Path):
    """Run the two roles. The fixture menu text is what the desk returns."""
    task, transcript, menu = read_fixtures()
    desk = OrderDesk(menu)
    if named:
        monitor = ScriptedMonitor(
            trigger_kind="claim",
            trigger_contains="ask counter",
            escalate_to="counter",
        )
    else:
        monitor = ScriptedMonitor(trigger_kind=None)
    result = run_order_crew(monitor, taker_llm, make_counter, desk, task, transcript)
    sandbox.mkdir(parents=True, exist_ok=True)
    (sandbox / "order-package.txt").write_text(result.package, encoding="utf-8")
    return result, analyze(result, sandbox), desk


def dump_analysis(label: str, payload: dict, *, out_dir: Path | None = None) -> Path:
    dest = out_dir or (RUNS / "last-fake")
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{label}.json"
    body = {"label": label, "at": datetime.now(timezone.utc).isoformat(), **payload}
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CrewAI order package cookbook")
    parser.add_argument("--sandbox", type=Path, default=DEFAULT_SANDBOX / "live")
    args = parser.parse_args(argv)
    _load_dotenv(REPO / ".env")
    if not (os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")):
        print("skip live: no LLM_API_KEY")
        return 0
    task, transcript, menu = read_fixtures()
    monitor = ScriptedMonitor(trigger_kind="claim", trigger_contains="counter", escalate_to="counter")
    result = run_live_order(monitor, OrderDesk(menu), task, transcript)
    args.sandbox.mkdir(parents=True, exist_ok=True)
    (args.sandbox / "order-package.txt").write_text(result.package, encoding="utf-8")
    payload = analyze(result, args.sandbox)
    path = dump_analysis("live_order", payload, out_dir=RUNS / "last-live")
    print("escalate_to", payload["escalate_to"])
    print("counter_ran", payload["counter_ran"])
    print("first_answer", payload["first_answer"])
    print("analysis_json", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
