"""Run the shop chat in this folder, using the rule fixture."""

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

from config import BAD, CONTINUATION, CONTINUED, DEFAULT_SANDBOX, FIXTURES, RUNS, SHOP_DOCUMENT  # noqa: E402
from graph import RuleDesk, run_live_shop, run_shop_chat  # noqa: E402


def read_fixtures() -> tuple[str, str, str]:
    task = (FIXTURES / "task.txt").read_text(encoding="utf-8").strip()
    rule = (FIXTURES / "rule.txt").read_text(encoding="utf-8").strip()
    question = (FIXTURES / "question.txt").read_text(encoding="utf-8").strip()
    return task, rule, question


def analyze(result, sandbox: Path) -> dict:
    package_path = sandbox / "consult-package.txt"
    first = result.first
    last = result.history[-1].content if result.history else ""
    return {
        "consult_to": "" if first is None else first.consult_to,
        "first_answer": None if first is None else first.committed_answer,
        "resumed": None if result.resumed is None else result.resumed.committed_answer,
        "package": result.package,
        "same_chat": bool(result.history) and BAD not in last,
        "package_path": str(package_path),
    }


def run_cookbook(*, named: bool, assistant, make_checker, sandbox: Path, history: list | None = None):
    """Run this chat. The fixture rule is what the desk returns."""
    task, rule, question = read_fixtures()
    history = [] if history is None else history
    desk = RuleDesk(rule)
    if named:
        monitor = ScriptedMonitor(
            trigger_kind="claim",
            trigger_contains="ask the checker",
            consult_to="checker",
        )
    else:
        monitor = ScriptedMonitor(trigger_kind=None)
    result = run_shop_chat(monitor, assistant, history, question, make_checker, desk, task)
    sandbox.mkdir(parents=True, exist_ok=True)
    (sandbox / "consult-package.txt").write_text(result.package, encoding="utf-8")
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
    parser = argparse.ArgumentParser(description="LangChain rule consult cookbook")
    parser.add_argument("--sandbox", type=Path, default=DEFAULT_SANDBOX / "live")
    args = parser.parse_args(argv)
    _load_dotenv(REPO / ".env")
    if not (os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")):
        print("skip live: no LLM_API_KEY")
        return 0
    task, rule, question = read_fixtures()
    monitor = ScriptedMonitor(trigger_kind="claim", trigger_contains="checker", consult_to="checker")
    result = run_live_shop(monitor, RuleDesk(rule), task, question)
    args.sandbox.mkdir(parents=True, exist_ok=True)
    (args.sandbox / "consult-package.txt").write_text(result.package, encoding="utf-8")
    payload = analyze(result, args.sandbox)
    path = dump_analysis("live_rule", payload, out_dir=RUNS / "last-live")
    print("consult_to", payload["consult_to"])
    print("first_answer", payload["first_answer"])
    print("same_chat", payload["same_chat"])
    print("analysis_json", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
