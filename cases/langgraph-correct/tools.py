"""Practitioner BaseTool wrapping the lab sandbox writer."""

from __future__ import annotations

from pathlib import Path

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr

from interrupthink import SandboxWriteTool


class WriteArgs(BaseModel):
    path: str = Field(description="Relative path under the sandbox root")
    content: str = Field(description="File body to write")


class WriteHostTool(BaseTool):
    name: str = "write"
    description: str = "Write a file under the specialist sandbox."
    args_schema: type[BaseModel] = WriteArgs
    _inner: SandboxWriteTool = PrivateAttr()

    def __init__(self, inner: SandboxWriteTool, **kwargs) -> None:
        super().__init__(**kwargs)
        self._inner = inner

    def _run(self, path: str, content: str, **_kwargs) -> str:
        return str(self._inner.execute("write", {"path": path, "content": content}))


def build_write_tool(sandbox: Path) -> tuple[SandboxWriteTool, WriteHostTool]:
    inner = SandboxWriteTool(sandbox)
    return inner, WriteHostTool(inner)
