"""Fixture paths and the scripted order transcript."""

from __future__ import annotations

from pathlib import Path

CASE_DIR = Path(__file__).resolve().parent
FIXTURES = CASE_DIR / "fixtures"
DEFAULT_SANDBOX = CASE_DIR / "tmp"
RUNS = CASE_DIR / "runs"

BAD = "Order placed: cone with bacon."
ORDER_DOCUMENT = (
    '<step kind="tool_intent" reversible="true">'
    '{"name":"read_order","args":{"transcript":"cone with bacon"}}</step>\n'
    '<step kind="tool_intent" reversible="true">'
    '{"name":"place_order","args":{"item":"cone with bacon"}}</step>\n'
    '<step kind="claim">ask counter</step>\n'
    "<answer>" + BAD + "</answer>\n"
)
