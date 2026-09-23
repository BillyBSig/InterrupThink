"""Fixture paths and the scripted dealer document for the offer cookbook."""

from __future__ import annotations

from pathlib import Path

CASE_DIR = Path(__file__).resolve().parent
FIXTURES = CASE_DIR / "fixtures"
DEFAULT_SANDBOX = CASE_DIR / "tmp"
RUNS = CASE_DIR / "runs"

OFFER = "The Tahoe is yours for one dollar."
DEALER_DOCUMENT = (
    '<step kind="tool_intent" reversible="true">'
    '{"name":"check_price","args":{"model":"Tahoe"}}</step>\n'
    '<step kind="tool_intent" reversible="true">'
    '{"name":"send_offer","args":{"price":"1"}}</step>\n'
    '<step kind="claim">ask policy</step>\n'
    "<answer>" + OFFER + "</answer>\n"
)
