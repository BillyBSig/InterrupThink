from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from interrupthink.monitor.verdict import STATUSES, parse_supervisor_payload, supervisor_text_format
from interrupthink.parse.steps import ThoughtUnit
from interrupthink.runtime.events import Patch, Verdict

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
    """Report that no step contradicts the memo.

    Args:
        _unit: Ignored.

    Returns:
        False.
    """
    return False


class LlmMonitor:
    """Supervisor that judges one step at a time.

    Pass ``ask`` to supply verdicts from tests. Leave ``ask`` unset to
    call a live model. The live call blocks until that step is judged.
    Specialist generation does not continue underneath it.

    A missing or malformed supervisor response becomes ``Unknown``.
    ``Unknown`` does not interrupt and does not commit an answer.

    Attributes:
        ask: Optional function that returns a verdict payload for one step.
        memo: Private note the specialist does not see.
        instructions: Supervisor prompt used by the live path.
        mismatch: Predicate recorded with a ``False`` verdict. A rejection
            increments ``false_interrupt_count``. The cut still happens.
        default_missing: Fact used when a live ``False`` omits ``missing``.
        default_directive: Instruction used when a live ``False`` omits
            ``directive``.
        budget: How many interrupts this monitor may spend.
        askable: Step kinds that are sent to the supervisor. Other kinds
            return ``Unknown``.
        held_tool_ids: Identifiers reserved for the monitor protocol.
        interrupts_used: Interrupts already spent.
        calls: How many times the supervisor has been asked.
    """

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
        """Store the supervisor settings.

        Args:
            ask: Test double that returns a verdict payload. ``None``
                calls the live provider.
            memo: Private note included in the live request.
            instructions: Supervisor prompt. The default asks for JSON
                and treats ``Unknown`` as the neutral status.
            mismatch: Predicate recorded with a ``False`` verdict.
            default_missing: Fallback fact for a live ``False``.
            default_directive: Fallback instruction for a live ``False``.
            budget: Maximum interrupts this monitor may spend.
            model: Supervisor model. Defaults to ``SUPERVISOR_MODEL``.
            effort: Reasoning effort. Defaults to
                ``SUPERVISOR_REASONING_EFFORT``.
            api_key: Defaults to ``SUPERVISOR_API_KEY`` or
                ``OPENAI_API_KEY``.
            base_url: Defaults to ``SUPERVISOR_BASE_URL`` or the OpenAI API.
            askable: Step kinds that may be sent to the supervisor.
        """
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
        """Create a live monitor using credentials from the environment.

        Returns:
            A monitor with ``ask`` unset, so ``verdict`` calls the provider.
        """
        return cls(ask=None)

    def verdict(self, unit: ThoughtUnit) -> Verdict:
        """Judge one step.

        Kinds outside ``askable`` return ``Unknown`` without a provider
        call. The live path waits for the provider before the session
        continues.

        Args:
            unit: Step to judge.

        Returns:
            ``Unknown``, ``Ok``, ``Patch``, or ``False``. ``False`` carries
            a patch and a rollback checkpoint.

        Raises:
            RuntimeError: The live path has no API key, or the provider
                returns an HTTP error.
        """
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
        """Allow a held tool step to proceed.

        Args:
            unit_id: Identifier of the held tool step.

        Returns:
            An ``Ok`` verdict for that identifier.
        """
        return Verdict(unit_id=unit_id, status="Ok", reason="tool gate released")

    def _ask(self, unit: ThoughtUnit) -> dict[str, Any]:
        """Return a verdict payload for one step.

        Args:
            unit: Step to judge.

        Returns:
            A dictionary with at least ``status``. A non-dictionary from
            ``ask`` becomes ``Unknown``.
        """
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
    """Ask the live supervisor for one step.

    Args:
        model: Supervisor model.
        effort: Reasoning effort.
        api_key: Bearer token.
        base_url: API root.
        memo: Private note.
        unit: Step being judged.
        instructions: Supervisor prompt.

    Returns:
        The provider's text.

    Raises:
        RuntimeError: No API key is configured.
    """
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
    """Call the Responses endpoint and return the assistant text.

    Args:
        model: Model name.
        effort: Reasoning effort.
        api_key: Bearer token.
        base_url: API root.
        instructions: System text.
        user: User text.
        timeout_s: Socket timeout.
        json_schema: When true, the request asks for the supervisor schema.

    Returns:
        The assistant text from the payload.

    Raises:
        RuntimeError: No API key is configured, or the provider returns
            an HTTP error.
    """
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
    """Build a blocking Responses body.

    Args:
        model: Model name.
        effort: Reasoning effort.
        instructions: System text.
        user: User text.
        json_schema: When true, attach the supervisor JSON schema.

    Returns:
        The request body. It does not include a stream flag.
    """
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
    """Read the assistant text from a Responses payload.

    Args:
        payload: JSON object returned by the provider.

    Returns:
        ``output_text`` when it is present. Otherwise the text parts of
        message output.
    """
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
