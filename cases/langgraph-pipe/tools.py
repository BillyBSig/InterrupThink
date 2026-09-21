"""Case-local fixture reader. Not a library retriever. Not DummyTool."""

from __future__ import annotations

from pathlib import Path


class FixtureRetrieveTool:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self.calls: list[dict] = []
        self.retrieved: list[str] = []

    def execute(self, name: str, args: dict) -> str:
        payload = {"name": name, "args": dict(args or {})}
        self.calls.append(payload)
        if name != "retrieve":
            raise ValueError(f"unsupported retrieve tool: {name}")
        rel = str((args or {}).get("path") or "current.txt")
        dest = (self.root / rel).resolve()
        try:
            dest.relative_to(self.root)
        except ValueError:
            raise ValueError(f"path escapes fixtures: {rel}") from None
        text = dest.read_text(encoding="utf-8")
        self.retrieved.append(text)
        return text
