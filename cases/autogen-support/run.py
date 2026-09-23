"""Run the support chat in this folder, using the held-reply fixture."""

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

from config import DEFAULT_SANDBOX, FIXTURES, OFF_TASK, RUNS, SUPPORT_DOCUMENT  # noqa: E402
from graph import SupportDesk, run_live_support, run_support_chat  # noqa: E402


def read_fixtures() -> tuple[str, str]:
    task = (FIXTURES / "task.txt").read_text(encoding="utf-8").strip()
    held = (FIXTURES / "held.txt").read_text(encoding="utf-8").strip()
    return task, held


def analyze(result, sandbox: Path) -> dict:
    package_path = sandbox / "human-package.txt"
    first = result.first
    return {
        "takeover_to": "" if first is None else first.takeover_to,
        "agents": list(result.agents),
        "first_answer": None if first is None else first.committed_answer,
        "package": result.package,
        "package_path": str(package_path),
    }


def run_cookbook(*, named: bool, agent_llm, sandbox: Path):
    """Run the one support agent. The fixture says the reply was not sent."""
    task, held = read_fixtures()
    desk = SupportDesk(held)
    if named:
        monitor = ScriptedMonitor(
            trigger_kind="claim",
            trigger_contains="the supervisor should take this",
            takeover_to="human",
        )
    else:
        monitor = ScriptedMonitor(trigger_kind=None)
    result = run_support_chat(monitor, agent_llm, desk, task)
    sandbox.mkdir(parents=True, exist_ok=True)
    (sandbox / "human-package.txt").write_text(result.package, encoding="utf-8")
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
    parser = argparse.ArgumentParser(description="AutoGen support takeover cookbook")
    parser.add_argument("--sandbox", type=Path, default=DEFAULT_SANDBOX / "live")
    args = parser.parse_args(argv)
    _load_dotenv(REPO / ".env")
    if not (os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")):
        print("skip live: no LLM_API_KEY")
        return 0
    task, held = read_fixtures()
    monitor = ScriptedMonitor(trigger_kind="claim", trigger_contains="supervisor", takeover_to="human")
    result = run_live_support(monitor, SupportDesk(held), task)
    args.sandbox.mkdir(parents=True, exist_ok=True)
    (args.sandbox / "human-package.txt").write_text(result.package, encoding="utf-8")
    payload = analyze(result, args.sandbox)
    path = dump_analysis("live_support", payload, out_dir=RUNS / "last-live")
    print("takeover_to", payload["takeover_to"])
    print("agents", payload["agents"])
    print("first_answer", payload["first_answer"])
    print("analysis_json", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
