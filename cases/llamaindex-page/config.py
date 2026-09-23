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
    '<step kind="tool_intent" reversible="true">'
    '{"name":"retrieve_page","args":{"query":"exchange after 30 days"}}</step>\n'
    '<step kind="claim">ask the checker</step>\n'
    "<answer>" + BAD + "</answer>\n"
)
CONTINUATION = (
    '<step kind="claim">the reply can be finished</step>\n'
    "<answer>" + CONTINUED + "</answer>\n"
)
