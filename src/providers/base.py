from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Llm(Protocol):
    tokens_emitted: int
    tokens_wasted: int

    def generate(self) -> str: ...

    def abort(self) -> None: ...

    def apply_resume(self, envelope: str | None) -> None:
        """Replay text for the next request. Not a KV-cache rewind."""
        ...
