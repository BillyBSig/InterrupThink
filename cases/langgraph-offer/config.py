"""Fixture paths and the scripted dealer document for the offer cookbook."""

from __future__ import annotations

from pathlib import Path

CASE_DIR = Path(__file__).resolve().parent
FIXTURES = CASE_DIR / "fixtures"
DEFAULT_SANDBOX = CASE_DIR / "tmp"
RUNS = CASE_DIR / "runs"

OFFER = "The Tahoe is yours for one dollar."
DEALER_DOCUMENT = (
    'tool_intent reversible: ' '{"name":"check_price","args":{"model":"Tahoe"}}\n'
    'tool_intent reversible: ' '{"name":"send_offer","args":{"price":"1"}}\n'
    'claim: ask policy\n'
    "answer: " + OFFER + "\n"
)
