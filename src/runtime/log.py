from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, TextIO

_REDACT_KEYS = frozenset({"text", "args", "prefix", "binding", "reason"})


class JsonlLogger:
    """JSONL session trace. Default redacts unit text, tool args, resume prefix, and monitor reason."""

    def __init__(
        self,
        path: Path | str | None = None,
        stream: TextIO | None = None,
        *,
        redact: bool = True,
    ) -> None:
        self.path = Path(path) if path else None
        self._stream = stream
        self.redact = redact
        self.records: list[dict[str, Any]] = []
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("", encoding="utf-8")

    def write(self, event: str, **fields: Any) -> dict[str, Any]:
        record = {"event": event, **_plain(fields)}
        if self.redact:
            record = _redact(record)
        self.records.append(record)
        line = json.dumps(record, ensure_ascii=False)
        if self.path:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        if self._stream:
            self._stream.write(line + "\n")
        return record


def _redact(record: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in record.items():
        if key in _REDACT_KEYS:
            out[key] = _redact_value(value)
        else:
            out[key] = value
    return out


def _redact_value(value: Any) -> Any:
    if value in (None, "", {}, []):
        return value
    if isinstance(value, dict):
        return {"redacted": True, "keys": sorted(str(k) for k in value)}
    if isinstance(value, str):
        return {"redacted": True, "chars": len(value)}
    return {"redacted": True}


def _plain(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value
