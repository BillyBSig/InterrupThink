"""Fixture paths and the scripted shop turn."""

from __future__ import annotations

from pathlib import Path

CASE_DIR = Path(__file__).resolve().parent
FIXTURES = CASE_DIR / "fixtures"
DEFAULT_SANDBOX = CASE_DIR / "tmp"
RUNS = CASE_DIR / "runs"

BAD = "You may skip the posted city rule."
CONTINUED = "The shop must follow the posted city rule."
SHOP_DOCUMENT = (
    '<step kind="tool_intent" reversible="true">'
    '{"name":"read_rule","args":{"topic":"posted city rule"}}</step>\n'
    '<step kind="claim">ask the checker</step>\n'
    "<answer>" + BAD + "</answer>\n"
)
CONTINUATION = (
    '<step kind="claim">the reply can be finished</step>\n'
    "<answer>" + CONTINUED + "</answer>\n"
)
