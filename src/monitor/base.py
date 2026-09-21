from __future__ import annotations

from typing import Protocol

from src.parse.steps import ThoughtUnit
from src.runtime.events import Verdict


class Monitor(Protocol):
    held_tool_ids: list[str]

    def verdict(self, unit: ThoughtUnit) -> Verdict: ...

    def release_tool(self, unit_id: str) -> Verdict: ...
