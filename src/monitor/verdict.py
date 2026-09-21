"""Supervisor verdict payload: JSON schema and local validation."""

from __future__ import annotations

import json
import re
from typing import Any

STATUSES = frozenset({"Unknown", "Ok", "Patch", "False"})

SUPERVISOR_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "status",
        "reason",
        "diagnosis",
        "missing",
        "directive",
        "rejects_q3_trend",
    ],
    "properties": {
        "status": {"type": "string", "enum": sorted(STATUSES)},
        "reason": {"type": "string"},
        "diagnosis": {"type": "string"},
        "missing": {"type": "string"},
        "directive": {"type": "string"},
        "rejects_q3_trend": {"type": "boolean"},
    },
}


def supervisor_text_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "name": "supervisor_verdict",
        "strict": True,
        "schema": SUPERVISOR_JSON_SCHEMA,
    }


def parse_supervisor_payload(text: str) -> dict[str, Any]:
    """JSON object → ask-dict. Garbage or unknown status → Unknown (never False)."""
    raw = _load_object(text)
    if raw is None:
        return {"status": "Unknown", "reason": "unparseable supervisor output"}
    status = str(raw.get("status") or "Unknown")
    if status not in STATUSES:
        status = "Unknown"
    return {
        "status": status,
        "reason": str(raw.get("reason") or ""),
        "diagnosis": str(raw.get("diagnosis") or ""),
        "missing": str(raw.get("missing") or ""),
        "directive": str(raw.get("directive") or ""),
        "rejects_q3_trend": bool(raw.get("rejects_q3_trend")),
    }


def _load_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped)
    parsed = _try_json(stripped)
    if parsed is None:
        match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if match is None:
            return None
        parsed = _try_json(match.group(0))
    if not isinstance(parsed, dict):
        return None
    return parsed


def _try_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
