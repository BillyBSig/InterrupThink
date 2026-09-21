from __future__ import annotations


class FakeLlm:
    """Deterministic specialist model for repeatable tests."""

    def __init__(self, documents: list[str]) -> None:
        self.documents = list(documents)
        self.request_index = 0
        self.aborted = False
        self.tokens_emitted = 0
        self.tokens_wasted = 0
        self.prefix: str | None = None
        self.resume_envelope: str = ""

    def generate(self) -> str:
        return "".join(self.iter_deltas())

    def iter_deltas(self):
        if self.request_index >= len(self.documents):
            raise IndexError("FakeLlm has no further documents")
        self.aborted = False
        text = self.documents[self.request_index]
        self.request_index += 1
        self.tokens_emitted += _rough_tokens(text)
        yield text

    def abort(self) -> None:
        self.aborted = True
        if self.request_index == 0:
            return
        last = self.documents[self.request_index - 1]
        self.tokens_wasted += _rough_tokens(last)

    def apply_resume(self, envelope: str | None) -> None:
        text = envelope or ""
        self.resume_envelope = text
        self.prefix = text or None


class DummyTool:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def execute(self, name: str, args: dict) -> str:
        self.calls.append({"name": name, "args": args})
        return "ok"


def _rough_tokens(text: str) -> int:
    return max(1, len(text.split()))
