"""Write files only under a sandbox root. Lab I/O analog — not git/DB production."""

from __future__ import annotations

from pathlib import Path


class SandboxWriteTool:
    """Like DummyTool, but execute('write') actually writes a file under root."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.calls: list[dict] = []
        self.written: list[str] = []
        self.rejected: list[str] = []

    def execute(self, name: str, args: dict) -> str:
        payload = {"name": name, "args": dict(args or {})}
        self.calls.append(payload)
        if name != "write":
            raise ValueError(f"unsupported sandbox tool: {name}")
        rel = str((args or {}).get("path") or "out.txt")
        content = str((args or {}).get("content") or "")
        dest = (self.root / rel).resolve()
        try:
            dest.relative_to(self.root)
        except ValueError:
            self.rejected.append(rel)
            raise ValueError(f"path escapes sandbox: {rel}") from None
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        self.written.append(str(dest.relative_to(self.root)))
        return f"wrote {dest.name}"
