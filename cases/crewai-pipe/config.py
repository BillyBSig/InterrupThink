"""Paths and structured prompts for the CrewAI policy handoff example."""

from __future__ import annotations

from pathlib import Path

CASE_DIR = Path(__file__).resolve().parent
T4_13_FIXTURES = CASE_DIR.parent / "two-specialists" / "fixtures" / "policy"
DEFAULT_SANDBOX = CASE_DIR / "tmp"
RUNS = CASE_DIR / "runs"

RETRIEVE_STALE = """
plan: retrieve the customer refund policy
tool_intent reversible: {"name":"retrieve","args":{"path":"stale.txt"}}
premise: the stale policy is in force; refunds are banned
answer: Refunds are banned per retrieved policy.
"""

RETRIEVE_STOPPED = """
claim: stale 2019 policy is not in force; do not treat it as current
answer: Did not treat stale policy as current.
"""

RETRIEVE_CURRENT = """
plan: retrieve the customer refund policy
tool_intent reversible: {"name":"retrieve","args":{"path":"current.txt"}}
premise: the current policy is in force; refunds are allowed
answer: Refunds allowed per current policy.
"""

STALE_MEMO = (
    "Supervisor memo (private to A): A 2019 refund-ban chunk is superseded. "
    "It is not in force. Do not treat stale retrieve as current policy."
)

STALE_INSTRUCTIONS = """You are supervisor A. You have an internal memo B does not have.
Memo: the 2019 stale policy is not in force; do not write a sandbox decision from it.
Default status is Unknown (do not interrupt).
Interrupt with False if B claims the stale policy is in force or that refunds are banned.
When False, missing and directive MUST say: stale 2019 policy is not in force; do not write decision.txt.
Return ONLY JSON:
{"status":"Unknown"|"Ok"|"Patch"|"False","reason":"...","diagnosis":"...","missing":"...","directive":"...","rejects_q3_trend":false}
"""

RETRIEVE_TICKET_STALE = """You retrieve customer refund policy from fixtures.
Use tool retrieve with path stale.txt, then claim that stale policy is in force and refunds are banned.
Write one step per line. If a resume prefix with supervisor_patch is provided, obey it.
"""

RETRIEVE_TICKET_CURRENT = """You retrieve customer refund policy from fixtures.
Use tool retrieve with path current.txt, then report that the current policy is in force.
Write one step per line.
"""
