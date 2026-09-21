from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree as ET

STEP_KINDS = frozenset(
    {
        "plan",
        "premise",
        "claim",
        "evidence",
        "tool_intent",
        "doubt",
        "answer_draft",
    }
)


class ParseError(ValueError):
    """LLM output is not a valid structured step document."""


@dataclass
class ThoughtUnit:
    id: str
    agent: str
    parent_id: str
    kind: str
    text: str
    state: str = "speculative"
    span: dict[str, int] | None = None
    reversible: bool | None = None  # model-declared intent; not host authorization
    tool: dict[str, Any] | None = None


@dataclass
class ParsedDocument:
    units: list[ThoughtUnit]
    answer: str | None = None


_STEP_TAG = re.compile(r"<step\b", re.IGNORECASE)


def parse_steps(raw: str, *, agent: str = "B", start_n: int = 1) -> ParsedDocument:
    if not raw or not raw.strip():
        raise ParseError("empty llm output")
    if _STEP_TAG.search(raw) is None:
        raise ParseError("no <step> element in llm output")

    wrapped = f"<doc>{raw.strip()}</doc>"
    try:
        root = ET.fromstring(wrapped)
    except ET.ParseError as exc:
        raise ParseError(f"invalid XML: {exc}") from exc

    units: list[ThoughtUnit] = []
    answer: str | None = None
    cursor = 0

    for child in list(root):
        tag = child.tag.lower()
        if tag == "step":
            unit, cursor = _step_to_unit(child, agent, units, raw, cursor, start_n)
            units.append(unit)
        elif tag == "answer":
            answer = (child.text or "").strip()
        else:
            raise ParseError(f"unexpected element <{child.tag}>")

    if not units:
        raise ParseError("no <step> element in llm output")
    return ParsedDocument(units=units, answer=answer or None)


def _step_to_unit(
    el: ET.Element,
    agent: str,
    prior: list[ThoughtUnit],
    raw: str,
    cursor: int,
    start_n: int,
) -> tuple[ThoughtUnit, int]:
    kind = (el.attrib.get("kind") or "").strip()
    if kind not in STEP_KINDS:
        raise ParseError(f"unknown step kind: {kind!r}")

    body = "".join(el.itertext()).strip()
    seq = start_n + len(prior)
    unit_id = f"tu_{seq:02d}"
    parent_id = prior[-1].id if prior else "tu_00"

    start = raw.find(body, cursor) if body else cursor
    if start < 0:
        start = cursor
    end = start + len(body)
    reversible: bool | None = None
    tool: dict[str, Any] | None = None
    if kind == "tool_intent":
        reversible = _parse_bool(el.attrib.get("reversible"), default=True)
        tool = _parse_tool_body(body)  # host policy uses (name, args), not reversible

    unit = ThoughtUnit(
        id=unit_id,
        agent=agent,
        parent_id=parent_id,
        kind=kind,
        text=body,
        span={"token_start": start, "token_end": end},
        reversible=reversible,
        tool=tool,
    )
    return unit, end


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    lowered = value.strip().lower()
    if lowered in {"true", "1", "yes"}:
        return True
    if lowered in {"false", "0", "no"}:
        return False
    raise ParseError(f"invalid reversible attribute: {value!r}")


def _parse_tool_body(body: str) -> dict[str, Any]:
    if not body:
        raise ParseError("tool_intent body must be JSON")
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ParseError(f"tool_intent JSON invalid: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ParseError("tool_intent JSON must be an object")
    return parsed
