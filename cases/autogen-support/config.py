"""Fixture paths and the scripted support turn."""

from __future__ import annotations

from pathlib import Path

CASE_DIR = Path(__file__).resolve().parent
FIXTURES = CASE_DIR / "fixtures"
DEFAULT_SANDBOX = CASE_DIR / "tmp"
RUNS = CASE_DIR / "runs"

OFF_TASK = "I will leave the parcel and complain about the company."
SUPPORT_DOCUMENT = (
    '<step kind="tool_intent" reversible="true">'
    '{"name":"hold_reply","args":{"topic":"parcel"}}</step>\n'
    '<step kind="claim">the supervisor should take this</step>\n'
    "<answer>" + OFF_TASK + "</answer>\n"
)
