"""Host tool that writes once for one logical step. No API key.

Scenario
    The first document writes a note, then states a false premise. The floor
    interrupts and asks again. The second document repeats the same tool name
    and arguments under a new ThoughtUnit id.

Flow
    ``FakeLlm`` + ``ScriptedMonitor`` + a host tool. The tool keeps an
    in-memory store keyed by tool name and arguments. That store stands in
    for a file or ticket the host owns.

Expected
    Two logical calls, one write. The interrupt does not clear the store.
    A new ThoughtUnit id on the resumed request is not a new write.

Usage (repo root; no API key)::

    pip install -e .
    python3 examples/host_idempotent_tool.py
"""

import hashlib
import json

from interrupthink import FakeLlm, ScriptedMonitor, run_session

FIRST = """
<step kind="tool_intent" reversible="true">{"name":"write_note","args":{"doc":"changelog"}}</step>
<step kind="premise">the changelog is already approved</step>
<answer>Published the changelog.</answer>
"""

SECOND = """
<step kind="tool_intent" reversible="true">{"name":"write_note","args":{"doc":"changelog"}}</step>
<step kind="claim">the note is already stored; do not publish</step>
<answer>Did not publish. The note stays.</answer>
"""


def step_key(name: str, args: dict) -> str:
    """Stable host key. A fresh unit id must not change this."""
    payload = json.dumps({"name": name, "args": args}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


class IdempotentNote:
    """Host-owned store. The floor does not clear it on rollback."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.writes = 0
        self.calls: list[dict] = []

    def execute(self, name: str, args: dict) -> str:
        key = step_key(name, args)
        self.calls.append({"name": name, "args": dict(args), "key": key})
        cached = self.store.get(key)
        if cached is not None:
            return cached
        self.writes += 1
        self.store[key] = f"stored:{name}"
        return self.store[key]


def run_idempotent_note():
    tool = IdempotentNote()
    result = run_session(
        llm=FakeLlm([FIRST, SECOND]),
        monitor=ScriptedMonitor(
            trigger_kind="premise",
            trigger_contains="already approved",
        ),
        tool=tool,
    )
    return result, tool


def main() -> None:
    result, tool = run_idempotent_note()
    print("interrupt_ids", result.interrupt_ids)
    print("writes", tool.writes)
    print("calls", len(tool.calls))
    print("store", list(tool.store.values()))
    print("answer", result.committed_answer)


if __name__ == "__main__":
    main()
