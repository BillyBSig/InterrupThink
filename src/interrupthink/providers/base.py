from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Llm(Protocol):
    """Specialist model used by one session.

    ``apply_resume`` receives text for the next request. It does not
    rewind provider state.

    Attributes:
        tokens_emitted: Rough count of text produced for the caller.
        tokens_wasted: Rough count charged when a request is aborted.
    """

    tokens_emitted: int
    tokens_wasted: int

    def generate(self) -> str:
        """Return the specialist document for this request.

        Returns:
            The full document, including its steps.
        """
        ...

    def abort(self) -> None:
        """Stop the current request.

        A successful provider cancel is not proof that generation stopped.
        """
        ...

    def apply_resume(self, envelope: str | None) -> None:
        """Store text the next request should see.

        This is context for a new request, not a rewind of provider state.

        Args:
            envelope: Resume prefix from the floor. ``None`` clears it.
        """
        ...
