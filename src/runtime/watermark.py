from dataclasses import dataclass


@dataclass
class Watermarks:
    checked_ok: str | None = None
    speculative_head: str | None = None
    committed_answer: str | None = None
