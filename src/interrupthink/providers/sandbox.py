"""Write files only under a sandbox root. Lab I/O analog — not git/DB production."""

from __future__ import annotations

from pathlib import Path


class SandboxWriteTool:
    """Write files only inside a sandbox directory.

    ``execute("write")`` creates the file. Any other name is rejected.
    A path that escapes the sandbox is rejected and recorded.

    Attributes:
        root: Absolute sandbox directory. It is created if missing.
        calls: Calls in execution order.
        written: Relative paths that were written.
        rejected: Relative paths refused because they escaped the sandbox.
    """

    def __init__(self, root: Path | str) -> None:
        """Create the sandbox directory.

        Args:
            root: Directory that will contain every written file.
        """
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.calls: list[dict] = []
        self.written: list[str] = []
        self.rejected: list[str] = []

    def execute(self, name: str, args: dict) -> str:
        """Write one file inside the sandbox.

        Args:
            name: Must be ``"write"``.
            args: ``path`` is the relative file name. ``content`` is the
                file text. Both may be omitted.

        Returns:
            ``"wrote {filename}"`` after the file is saved.

        Raises:
            ValueError: ``name`` is not ``"write"``, or ``path`` escapes
                the sandbox.
        """
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
