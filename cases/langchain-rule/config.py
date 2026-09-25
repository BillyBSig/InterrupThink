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
    'tool_intent reversible: ' '{"name":"read_rule","args":{"topic":"posted city rule"}}\n'
    'claim: ask the checker\n'
    "answer: " + BAD + "\n"
)
CONTINUATION = (
    'claim: the reply can be finished\n'
    "answer: " + CONTINUED + "\n"
)
