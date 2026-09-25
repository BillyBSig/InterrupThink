from dataclasses import dataclass


@dataclass
class Watermarks:
    """Positions the floor has reached in one request.

    Attributes:
        checked_ok: Last step the monitor accepted with ``Ok``.
        speculative_head: Newest step ingested and not yet dropped.
        committed_answer: Answer text committed after an ``Ok`` verdict.
            ``None`` until that commit happens.
    """

    checked_ok: str | None = None
    speculative_head: str | None = None
    committed_answer: str | None = None
