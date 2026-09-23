"""Run the offer graph in this folder, using the price fixture.

Reads the fixture, writes the package into a sandbox file, and stores a short
analysis under ``runs/``.
"""

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

from config import DEALER_DOCUMENT, DEFAULT_SANDBOX, FIXTURES, OFFER, RUNS  # noqa: E402
from graph import OfferDesk, run_live_offer, run_offer_graph  # noqa: E402


def read_fixtures() -> tuple[str, str]:
    task = (FIXTURES / "task.txt").read_text(encoding="utf-8").strip()
    price = (FIXTURES / "price.txt").read_text(encoding="utf-8").strip()
    return task, price


def analyze(result, sandbox: Path) -> dict:
    package_path = sandbox / "policy-package.txt"
    first = result.first
    return {
        "escalate_to": "" if first is None else first.escalate_to,
        "dealer_visits": result.dealer_visits,
        "policy_visits": result.policy_visits,
        "first_answer": None if first is None else first.committed_answer,
        "package": result.package,
        "package_path": str(package_path),
        "offer_in_package_file": OFFER in package_path.read_text(encoding="utf-8"),
    }


def run_cookbook(*, named: bool, dealer_llm, make_policy, sandbox: Path):
    """Run the two nodes in this folder. The fixture price is what the desk returns."""
    task, price = read_fixtures()
    desk = OfferDesk(price)
    if named:
        monitor = ScriptedMonitor(
            trigger_kind="claim",
            trigger_contains="ask policy",
            escalate_to="policy",
        )
    else:
        monitor = ScriptedMonitor(trigger_kind=None)
    result = run_offer_graph(monitor, dealer_llm, make_policy, desk, task)
    sandbox.mkdir(parents=True, exist_ok=True)
    (sandbox / "policy-package.txt").write_text(result.package, encoding="utf-8")
    return result, analyze(result, sandbox)


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
    parser = argparse.ArgumentParser(description="LangGraph offer package cookbook")
    parser.add_argument("--sandbox", type=Path, default=DEFAULT_SANDBOX / "live")
    args = parser.parse_args(argv)
    _load_dotenv(REPO / ".env")
    if not (os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")):
        print("skip live: no LLM_API_KEY")
        return 0
    task, price = read_fixtures()
    monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="policy",
        escalate_to="policy",
    )
    result = run_live_offer(monitor, OfferDesk(price), task)
    args.sandbox.mkdir(parents=True, exist_ok=True)
    (args.sandbox / "policy-package.txt").write_text(result.package, encoding="utf-8")
    payload = analyze(result, args.sandbox)
    path = dump_analysis("live_offer", payload, out_dir=RUNS / "last-live")
    print("escalate_to", payload["escalate_to"])
    print("policy_visits", payload["policy_visits"])
    print("first_answer", payload["first_answer"])
    print("analysis_json", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
