from __future__ import annotations


class FakeLlm:
    """Specialist model that yields canned documents, one request at a time.

    ``apply_resume`` stores the envelope. ``iter_deltas`` ignores that
    envelope and yields the next canned document. Tests that need a second
    request must supply a second document.

    Attributes:
        documents: Canned specialist documents, in request order.
        request_index: How many documents have been started.
        aborted: Whether ``abort`` was called during the latest request.
        tokens_emitted: Rough token count of text yielded so far.
        tokens_wasted: Rough token count charged by ``abort``.
        prefix: Resume envelope from the latest ``apply_resume``.
        resume_envelope: Same text as ``prefix``, or ``""`` when no
            envelope was applied.
    """

    def __init__(self, documents: list[str]) -> None:
        """Store the canned documents.

        Args:
            documents: One specialist document per request, in order.
                The list is copied.
        """
        self.documents = list(documents)
        self.request_index = 0
        self.aborted = False
        self.tokens_emitted = 0
        self.tokens_wasted = 0
        self.prefix: str | None = None
        self.resume_envelope: str = ""

    def generate(self) -> str:
        """Return the next canned document as one string.

        Returns:
            The document for this request.

        Raises:
            IndexError: Every canned document has already been used.
        """
        return "".join(self.iter_deltas())

    def iter_deltas(self):
        """Yield the next canned document as a single chunk.

        Yields:
            The full text of the next document.

        Raises:
            IndexError: Every canned document has already been used.
        """
        if self.request_index >= len(self.documents):
            raise IndexError("FakeLlm has no further documents")
        self.aborted = False
        text = self.documents[self.request_index]
        self.request_index += 1
        self.tokens_emitted += _rough_tokens(text)
        yield text

    def abort(self) -> None:
        """Mark the current request aborted and count its text as wasted.

        A call before the first document does not add wasted tokens.
        """
        self.aborted = True
        if self.request_index == 0:
            return
        last = self.documents[self.request_index - 1]
        self.tokens_wasted += _rough_tokens(last)

    def apply_resume(self, envelope: str | None) -> None:
        """Store the resume envelope for later inspection.

        The next ``iter_deltas`` call still yields the next canned
        document. It does not splice the envelope into that document.

        Args:
            envelope: Resume text from the floor. ``None`` stores an
                empty envelope.
        """
        text = envelope or ""
        self.resume_envelope = text
        self.prefix = text or None


class DummyTool:
    """Tool that records calls and returns ``"ok"``.

    The return value is not stored on the call. A host that needs the
    result inside a handoff package must record it on the call itself.

    Attributes:
        calls: Calls in execution order. Each item has ``name`` and ``args``.
    """

    def __init__(self) -> None:
        """Start with an empty call list."""
        self.calls: list[dict] = []

    def execute(self, name: str, args: dict) -> str:
        """Record one call.

        Args:
            name: Tool name.
            args: Arguments supplied by the specialist.

        Returns:
            The string ``"ok"``.
        """
        self.calls.append({"name": name, "args": args})
        return "ok"


def _rough_tokens(text: str) -> int:
    """Count words as a stand-in for tokens.

    Args:
        text: Specialist text.

    Returns:
        At least one.
    """
    return max(1, len(text.split()))
