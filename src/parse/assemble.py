from __future__ import annotations

import re

_STEP = re.compile(r"<step\b[^>]*>.*?</step>", re.IGNORECASE | re.DOTALL)
_ANSWER = re.compile(r"<answer\b[^>]*>.*?</answer>", re.IGNORECASE | re.DOTALL)
_FENCE = re.compile(r"^```(?:xml)?\s*", re.IGNORECASE)

DEFAULT_MAX_BYTES = 256_000


class StepAssembler:
    """Yield complete <step> / <answer> blocks from a stream of text deltas."""

    def __init__(self, *, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
        self.buf = ""
        self.max_bytes = max_bytes

    def feed(self, delta: str) -> list[str]:
        self.buf += delta
        self.buf = _FENCE.sub("", self.buf.lstrip())
        if self.buf.endswith("```"):
            self.buf = self.buf[: -3].rstrip()
        out: list[str] = []
        while True:
            text = _lstrip_to_tag(self.buf)
            if text is None:
                break
            step = _STEP.match(text)
            answer = _ANSWER.match(text)
            taken = None
            if step and (answer is None or step.start() <= answer.start()) and step.start() == 0:
                taken = step
            elif answer and answer.start() == 0:
                taken = answer
            if taken is None:
                self.buf = text
                break
            out.append(taken.group(0))
            self.buf = text[taken.end() :]
        if len(self.buf) > self.max_bytes:
            from src.runtime.session import SessionError

            raise SessionError(
                f"stream assembler exceeded buffer cap ({self.max_bytes} bytes)"
            )
        return out


def is_answer_fragment(xml: str) -> bool:
    return xml.lstrip().lower().startswith("<answer")


def answer_text(xml: str) -> str:
    match = _ANSWER.search(xml)
    if not match:
        return xml.strip()
    inner = re.sub(r"^<answer\b[^>]*>", "", match.group(0), flags=re.IGNORECASE)
    inner = re.sub(r"</answer>\s*$", "", inner, flags=re.IGNORECASE)
    return inner.strip()


def _lstrip_to_tag(buf: str) -> str | None:
    lower = buf.lower()
    idx_step = lower.find("<step")
    idx_ans = lower.find("<answer")
    candidates = [i for i in (idx_step, idx_ans) if i >= 0]
    if not candidates:
        return None
    return buf[min(candidates) :]
