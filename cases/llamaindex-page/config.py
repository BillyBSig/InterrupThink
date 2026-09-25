"""Fixture paths and the scripted exchange question."""

from __future__ import annotations

from pathlib import Path

CASE_DIR = Path(__file__).resolve().parent
FIXTURES = CASE_DIR / "fixtures"
DEFAULT_SANDBOX = CASE_DIR / "tmp"
RUNS = CASE_DIR / "runs"

BAD = "Yes, exchanges are available any time."
CONTINUED = "Exchanges after 30 days are not offered."
PAGE_DOCUMENT = (
    'tool_intent reversible: ' '{"name":"retrieve_page","args":{"query":"exchange after 30 days"}}\n'
    'claim: ask the checker\n'
    "answer: " + BAD + "\n"
)
CONTINUATION = (
    'claim: the reply can be finished\n'
    "answer: " + CONTINUED + "\n"
)
