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
    """The specialist output is not a valid step document.

    Raised for empty text, text with no step, unknown step kinds, and
    tool steps whose body is not a JSON object.
    """


@dataclass
class ThoughtUnit:
    """One checkable step from a specialist document.

    The interrupt boundary is this step, not a raw token. ``reversible``
    is the model's own label for a tool step. The host decides whether
    the tool may run.

    Attributes:
        id: Stable identifier, such as ``"tu_01"``.
        agent: Specialist that produced the step.
        parent_id: Previous step, or ``"tu_00"`` for the first step.
        kind: One of ``plan``, ``premise``, ``claim``, ``evidence``,
            ``tool_intent``, ``doubt``, or ``answer_draft``.
        text: Step body.
        state: ``"speculative"`` until the floor marks it checked or
            rejected.
        span: Character offsets of the body in the source text.
        reversible: Model label for a tool step. ``None`` for other kinds.
        tool: Parsed tool body for a ``tool_intent``. ``None`` otherwise.
    """

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
    """Steps from one specialist document, plus an optional answer.

    Attributes:
        units: Steps in document order.
        answer: Text of the ``<answer>`` element, or ``None`` when the
            document has no answer.
    """

    units: list[ThoughtUnit]
    answer: str | None = None


_STEP_TAG = re.compile(r"<step\b", re.IGNORECASE)


def parse_steps(raw: str, *, agent: str = "B", start_n: int = 1) -> ParsedDocument:
    """Parse a specialist XML document into steps.

    Args:
        raw: Specialist text. Markdown fences are not stripped here.
        agent: Name stored on each step. Defaults to ``"B"``.
        start_n: Number used for the first step identifier.

    Returns:
        The steps and the optional answer.

    Raises:
        ParseError: The text is empty, has no step, contains an unexpected
            element, or is not valid XML of the expected shape.
    """
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
    """Build one unit from a step element.

    Args:
        el: Parsed step element.
        agent: Name stored on the unit.
        prior: Steps already built from this document.
        raw: Original specialist text, used for the character span.
        cursor: Character offset to search from.
        start_n: Number of the first step in this document.

    Returns:
        The unit and the character offset just after its body.

    Raises:
        ParseError: The kind is unknown, or a tool body is not a JSON object.
    """
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
    """Read a reversible attribute.

    Args:
        value: Attribute text. ``None`` means the attribute was omitted.
        default: Value used when the attribute is omitted.

    Returns:
        The parsed boolean.

    Raises:
        ParseError: The attribute is present but not a recognized boolean.
    """
    if value is None:
        return default
    lowered = value.strip().lower()
    if lowered in {"true", "1", "yes"}:
        return True
    if lowered in {"false", "0", "no"}:
        return False
    raise ParseError(f"invalid reversible attribute: {value!r}")


def _parse_tool_body(body: str) -> dict[str, Any]:
    """Parse a tool step body as a JSON object.

    Args:
        body: Text inside the tool step.

    Returns:
        The object. The host uses ``name`` and ``args`` from it.

    Raises:
        ParseError: The body is empty, is not JSON, or is not an object.
    """
    if not body:
        raise ParseError("tool_intent body must be JSON")
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ParseError(f"tool_intent JSON invalid: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ParseError("tool_intent JSON must be an object")
    return parsed
