"""Build a resume transcript that keeps executed tool results.

The default text prefix is unchanged. This builder is used only when a
specialist opts in. An executed tool step that was kept becomes a
function call plus the exact text the tool returned. A dropped step is
omitted. Other kept steps stay plain lines.
"""

from __future__ import annotations

import json

from interrupthink.parse.steps import ThoughtUnit
from interrupthink.runtime.floor import _unit_line

_WRAPPER = "Resume prefix (do not repeat dropped text):\n"


def build_resume_input(
    prompt: str,
    units: list[ThoughtUnit],
    dropped_ids: set[str],
) -> list[dict]:
    """Return the provider input for one resume.

    Args:
        prompt: Original task text. It is not replaced.
        units: Floor steps in order.
        dropped_ids: Steps the rollback removed.

    Returns:
        Input items. With nothing kept, the list is the prompt alone.
        Otherwise the first item is the prompt, the resume wrapper, and
        any text that comes before the first kept tool. Each kept
        executed tool is the next pair of items. Later text steps follow
        in their own item.
    """
    kept = [unit for unit in units if unit.id not in dropped_ids]
    if not kept:
        return [{"role": "user", "content": prompt}]

    items: list[dict] = []
    text: list[str] = []
    opened = False

    def flush() -> None:
        nonlocal opened
        body = "\n".join(text)
        text.clear()
        if not opened:
            opened = True
            items.append({"role": "user", "content": f"{prompt}\n\n{_WRAPPER}{body}"})
        elif body:
            items.append({"role": "user", "content": body})

    for unit in kept:
        if unit.kind == "tool_intent" and unit.tool_result is not None:
            flush()
            call_id = f"kept_{unit.id}"
            payload = unit.tool or {}
            args = payload.get("args") or {}
            items.append(
                {
                    "type": "function_call",
                    "call_id": call_id,
                    "name": str(payload.get("name") or "unknown"),
                    "arguments": json.dumps(args, sort_keys=True, separators=(",", ":")),
                }
            )
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": unit.tool_result,
                }
            )
        else:
            text.append(_unit_line(unit))
    flush()
    return items
