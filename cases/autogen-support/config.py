"""Fixture paths and the scripted support turn."""

from __future__ import annotations

from pathlib import Path

CASE_DIR = Path(__file__).resolve().parent
FIXTURES = CASE_DIR / "fixtures"
DEFAULT_SANDBOX = CASE_DIR / "tmp"
RUNS = CASE_DIR / "runs"

OFF_TASK = "I will leave the parcel and complain about the company."
SUPPORT_DOCUMENT = (
    'tool_intent reversible: ' '{"name":"hold_reply","args":{"topic":"parcel"}}\n'
    'claim: the supervisor should take this\n'
    "answer: " + OFF_TASK + "\n"
)
