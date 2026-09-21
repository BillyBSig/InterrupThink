from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from src.monitor.verdict import STATUSES, parse_supervisor_payload, supervisor_text_format
from src.parse.steps import ThoughtUnit
from src.runtime.events import Patch, Verdict

ASKABLE = frozenset({"premise", "claim", "tool_intent", "answer_draft"})

AskFn = Callable[[ThoughtUnit], dict[str, Any]]

_DEFAULT_SUPERVISOR_INSTRUCTIONS = """You are a supervisor reviewing one ThoughtUnit from a specialist.
You have a private memo the specialist does not have.
Default status is Unknown (do not interrupt).
Interrupt with False only when the unit contradicts the memo.
Return ONLY JSON:
{"status":"Unknown"|"Ok"|"Patch"|"False","reason":"...","diagnosis":"...","missing":"...","directive":"...","rejects_q3_trend":true|false}
"""


def _never_mismatch(_unit: ThoughtUnit) -> bool:
    return False


class LlmMonitor:
    """On-demand supervisor. Live ``verdict`` is blocking HTTP per ThoughtUnit."""

    def __init__(
        self,
        *,
        ask: AskFn | None = None,
        memo: str = "",
        instructions: str | None = None,
        mismatch: Callable[[ThoughtUnit], bool] | None = None,
        default_missing: str = "",
        default_directive: str = "",
        budget: int = 2,
        model: str | None = None,
        effort: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        askable: frozenset[str] | set[str] | None = None,
    ) -> None:
        self.ask = ask
        self.memo = memo
        self.instructions = (
            instructions if instructions is not None else _DEFAULT_SUPERVISOR_INSTRUCTIONS
        )
        self.mismatch = mismatch if mismatch is not None else _never_mismatch
        self.default_missing = default_missing
        self.default_directive = default_directive
        self.budget = budget
        self.askable = frozenset(askable) if askable is not None else ASKABLE
        self.model = model or os.environ.get("SUPERVISOR_MODEL", "gpt-5.6-luna")
        self.effort = effort or os.environ.get("SUPERVISOR_REASONING_EFFORT", "medium")
        self.api_key = api_key or os.environ.get("SUPERVISOR_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self.base_url = (
            base_url or os.environ.get("SUPERVISOR_BASE_URL") or "https://api.openai.com/v1"
        ).rstrip("/")
        self.held_tool_ids: list[str] = []
        self.interrupts_used = 0
        self.false_interrupt_count = 0
        self.tokens_a = 0
        self.last_diagnosis: str | None = None
        self.last_rejects_q3 = False
        self.t_first_false: float | None = None
        self.calls = 0

    @classmethod
    def from_env(cls) -> LlmMonitor:
        """Create a live monitor using credentials from the environment."""
        return cls(ask=None)

    def verdict(self, unit: ThoughtUnit) -> Verdict:
        """Judge one unit. The live path waits on the provider; it does not overlap generation."""
        if unit.kind not in self.askable:
            return Verdict(unit_id=unit.id, status="Unknown", reason="filter: kind not askable")
        if self.interrupts_used >= self.budget:
            return Verdict(unit_id=unit.id, status="Unknown", reason="interrupt budget exhausted")

        payload = self._ask(unit)
        status = str(payload.get("status") or "Unknown")
        if status not in STATUSES:
            status = "Unknown"
        reason = str(payload.get("reason") or "")
        rejects = bool(payload.get("rejects_q3_trend"))
        diagnosis = str(payload.get("diagnosis") or reason)

        if status == "False":
            if diagnosis and diagnosis == self.last_diagnosis:
                return Verdict(unit_id=unit.id, status="Unknown", reason="anti-oscillation")
            if not self.mismatch(unit):
                self.false_interrupt_count += 1
            self.interrupts_used += 1
            self.last_diagnosis = diagnosis
            self.last_rejects_q3 = rejects or self.mismatch(unit)
            if self.t_first_false is None:
                self.t_first_false = time.monotonic()
            rollback_to = unit.parent_id
            patch = Patch(
                from_agent="A",
                target_unit_id=unit.id,
                rollback_to=rollback_to,
                diagnosis=diagnosis or "premise contradicts supervisor memo",
                missing=str(payload.get("missing") or self.default_missing),
                directive=str(payload.get("directive") or self.default_directive),
                preserve=[rollback_to] if rollback_to else [],
            )
            return Verdict(
                unit_id=unit.id,
                status="False",
                reason=reason or "supervisor False",
                patch=patch,
                rollback_to=rollback_to,
            )

        if status == "Patch":
            patch = Patch(
                from_agent="A",
                target_unit_id=unit.id,
                rollback_to=None,
                diagnosis=diagnosis,
                missing=str(payload.get("missing") or ""),
                directive=str(payload.get("directive") or ""),
            )
            return Verdict(unit_id=unit.id, status="Patch", reason=reason, patch=patch)

        return Verdict(unit_id=unit.id, status=status, reason=reason or status.lower())

    def release_tool(self, unit_id: str) -> Verdict:
        return Verdict(unit_id=unit_id, status="Ok", reason="tool gate released")

    def _ask(self, unit: ThoughtUnit) -> dict[str, Any]:
        self.calls += 1
        if self.ask is not None:
            raw = self.ask(unit)
            return raw if isinstance(raw, dict) else {"status": "Unknown"}
        text = _complete_supervisor(
            model=self.model,
            effort=self.effort,
            api_key=self.api_key or "",
            base_url=self.base_url,
            memo=self.memo,
            instructions=self.instructions,
            unit=unit,
        )
        self.tokens_a += max(1, len(text.split()))
        return parse_supervisor_payload(text)


def _complete_supervisor(
    *,
    model: str,
    effort: str,
    api_key: str,
    base_url: str,
    memo: str,
    unit: ThoughtUnit,
    instructions: str,
) -> str:
    if not api_key:
        raise RuntimeError("missing SUPERVISOR_API_KEY or OPENAI_API_KEY")
    user = (
        f"{memo}\n\nB ThoughtUnit id={unit.id} kind={unit.kind}:\n{unit.text}\n"
        "JSON verdict only."
    )
    return complete_text(
        model=model,
        effort=effort,
        api_key=api_key,
        base_url=base_url,
        instructions=instructions,
        user=user,
        json_schema=True,
    )


def complete_text(
    *,
    model: str,
    effort: str,
    api_key: str,
    base_url: str,
    instructions: str,
    user: str,
    timeout_s: float = 120.0,
    json_schema: bool = False,
) -> str:
    if not api_key:
        raise RuntimeError("missing SUPERVISOR_API_KEY or OPENAI_API_KEY")
    body = responses_body(
        model=model,
        effort=effort,
        instructions=instructions,
        user=user,
        json_schema=json_schema,
    )
    req = urllib.request.Request(
        f"{base_url}/responses",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"supervisor HTTP {exc.code}: {detail}") from exc
    return _payload_text(payload)


def responses_body(
    *,
    model: str,
    effort: str,
    instructions: str,
    user: str,
    json_schema: bool = False,
) -> dict:
    body = {
        "model": model,
        "reasoning": {"effort": effort},
        "instructions": instructions,
        "input": user,
    }
    if json_schema:
        body["text"] = {"format": supervisor_text_format()}
    return body


def _payload_text(payload: dict) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct
    chunks: list[str] = []
    for item in payload.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for part in item.get("content") or []:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                chunks.append(part["text"])
    return "".join(chunks)
