from __future__ import annotations

import re

_STEP = re.compile(r"<step\b[^>]*>.*?</step>", re.IGNORECASE | re.DOTALL)
_ANSWER = re.compile(r"<answer\b[^>]*>.*?</answer>", re.IGNORECASE | re.DOTALL)
_FENCE = re.compile(r"^```(?:xml)?\s*", re.IGNORECASE)

DEFAULT_MAX_BYTES = 256_000


class StepAssembler:
    """Collect a text stream into complete step and answer blocks.

    Incomplete tags stay in the buffer. A buffer that grows past
    ``max_bytes`` raises ``SessionError``.

    Attributes:
        buf: Text that has not yet formed a complete block.
        max_bytes: Largest incomplete buffer that is allowed.
    """

    def __init__(self, *, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
        """Start with an empty buffer.

        Args:
            max_bytes: Largest incomplete buffer that is allowed.
                Defaults to 256_000.
        """
        self.buf = ""
        self.max_bytes = max_bytes

    def feed(self, delta: str) -> list[str]:
        """Accept one chunk and return any blocks that are now complete.

        Args:
            delta: Next piece of specialist text.

        Returns:
            Complete ``<step>`` and ``<answer>`` blocks, in stream order.
            An empty list when the buffer still holds a partial tag.

        Raises:
            SessionError: The incomplete buffer exceeds ``max_bytes``.
        """
        self.buf += delta
        self.buf = _FENCE.sub("", self.buf.lstrip())
        if self.buf.endswith("```"):
            self.buf = self.buf[: -3].rstrip()
        if not _has_xml_tag(self.buf):
            lines, self.buf = _complete_lines(self.buf)
            if len(self.buf) > self.max_bytes:
                from src.runtime.session import SessionError

                raise SessionError(
                    f"stream assembler exceeded buffer cap ({self.max_bytes} bytes)"
                )
            return lines
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
    """Return whether a complete block is an answer.

    Args:
        xml: One block from the assembler.

    Returns:
        True when the block is an answer line or an ``<answer`` tag.
    """
    stripped = xml.lstrip().lower()
    return stripped.startswith("<answer") or stripped.startswith("answer:")


def answer_text(xml: str) -> str:
    """Return the text inside an answer block.

    Args:
        xml: One block. A block without an answer tag is stripped and
            returned as-is.

    Returns:
        The inner text of ``<answer>``.
    """
    stripped = xml.strip()
    if stripped.lower().startswith("answer:"):
        return stripped.split(":", 1)[1].strip()
    match = _ANSWER.search(xml)
    if not match:
        return stripped
    inner = re.sub(r"^<answer\b[^>]*>", "", match.group(0), flags=re.IGNORECASE)
    inner = re.sub(r"</answer>\s*$", "", inner, flags=re.IGNORECASE)
    return inner.strip()


def _has_xml_tag(buf: str) -> bool:
    """Return whether the buffer still uses a step or answer tag."""
    lower = buf.lower()
    return "<step" in lower or "<answer" in lower


def _complete_lines(buf: str) -> tuple[list[str], str]:
    """Split finished plain lines and keep a trailing partial line.

    Args:
        buf: Specialist text that does not contain a step tag.

    Returns:
        Complete non-empty lines, and the unfinished tail.
    """
    if "\n" not in buf:
        return [], buf
    finished, tail = buf.rsplit("\n", 1)
    blocks: list[str] = []
    current: str | None = None
    for line in finished.split("\n"):
        if not line.strip():
            continue
        if line[0].isspace() and current is not None:
            current = f"{current}\n{line.rstrip()}"
            continue
        if current is not None:
            blocks.append(current)
        current = line.strip()
    if current is not None:
        blocks.append(current)
    return blocks, tail


def _lstrip_to_tag(buf: str) -> str | None:
    """Drop text that sits before the next step or answer tag.

    Args:
        buf: Incomplete specialist text.

    Returns:
        The buffer from the earliest tag, or ``None`` when neither tag
        is present yet.
    """
    lower = buf.lower()
    idx_step = lower.find("<step")
    idx_ans = lower.find("<answer")
    candidates = [i for i in (idx_step, idx_ans) if i >= 0]
    if not candidates:
        return None
    return buf[min(candidates) :]
