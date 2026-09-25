"""LlamaIndex integration: retrieve a policy chunk before writing a notice.

Scenario
    An application already has a LlamaIndex ``VectorStoreIndex``. The ticket
    asks the specialist to retrieve a refund policy and post ``notice.txt``.
    The supervisor knows that a 2019 ban chunk is stale.

Flow
    One ``run_session``. Tool ``retrieve`` calls
    ``index.as_retriever().retrieve(query)``. The thinking model is
    ``LiveLlm`` and the write remains ``SandboxWriteTool``.

Expected
    Stale index: interrupt; no ``notice.txt``.
    Current index: retrieve + one notice. Analysis under ``runs/``.

Usage (repo root; local venv)::

    pip install llama-index llama-index-llms-openai llama-index-embeddings-openai
    python3 cases/llamaindex-retrieve/run.py   # personal .env; do not uv-add
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

from config import DEFAULT_SANDBOX, RUNS  # noqa: E402
from graph import analyze, run_llamaindex_retrieve  # noqa: E402

analyze = analyze
run_llamaindex_retrieve = run_llamaindex_retrieve


def dump_analysis(label: str, payload: dict, *, out_dir: Path | None = None) -> Path:
    dest = out_dir or (RUNS / "last-live")
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{label}.json"
    body = {"label": label, "at": datetime.now(timezone.utc).isoformat(), **payload}
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _print(label: str, payload: dict, path: Path) -> None:
    print(f"== {label} ==")
    for key in (
        "interrupt_ids",
        "retrieve_calls",
        "write_calls",
        "notice_exists",
        "retriever_class",
        "committed_answer",
    ):
        print(key, payload.get(key))
    print("analysis_json", path)


def _has_live_key() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LlamaIndex stale retrieve")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args(argv)
    load_dotenv()
    if not _has_live_key():
        print("skip live: no OPENAI_API_KEY / LLM_API_KEY")
        return 0
    blocked = run_llamaindex_retrieve(
        interrupt_stale=True,
        sandbox=(args.root / "interrupt") if args.root else DEFAULT_SANDBOX / "live-interrupt",
    )
    a1 = analyze(blocked)
    p1 = dump_analysis("live_stale_interrupt", a1, out_dir=RUNS / "last-live")
    _print("live_stale_interrupt", a1, p1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
