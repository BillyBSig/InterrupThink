"""InterrupThink (IRTU): Interruptible Reasoning at Thought Units.

Small interruptible reasoning floor for an open-source Python library.
Import module: ``interrupthink``. Distribution: ``interrupthink``.
Default after a cut: rollback — inject a patch, drop the bad tail, continue
mid-stream. Restart is the fallback. The export list is not a frozen contract.
Licensed under the Apache License, Version 2.0.
"""

from interrupthink.monitor.base import Monitor
from interrupthink.monitor.llm import ASKABLE, LlmMonitor
from interrupthink.monitor.scripted import ScriptedMonitor
from interrupthink.parse.steps import ParseError, ParsedDocument, ThoughtUnit, parse_steps
from interrupthink.providers.base import Llm
from interrupthink.providers.fake import DummyTool, FakeLlm
from interrupthink.providers.live import LiveLlm, load_dotenv
from interrupthink.providers.sandbox import SandboxWriteTool
from interrupthink.runtime.events import Patch, Verdict
from interrupthink.runtime.handoff import Consult, Escalation, Takeover
from interrupthink.runtime.floor import Floor
from interrupthink.runtime.log import JsonlLogger
from interrupthink.runtime.session import SessionError, SpikeResult, run_session

# Export names for the package facade.
PUBLIC_API = (
    "ASKABLE",
    "Consult",
    "DummyTool",
    "Escalation",
    "FakeLlm",
    "Floor",
    "JsonlLogger",
    "Llm",
    "LiveLlm",
    "LlmMonitor",
    "Monitor",
    "ParseError",
    "ParsedDocument",
    "Patch",
    "SandboxWriteTool",
    "ScriptedMonitor",
    "SessionError",
    "SpikeResult",
    "Takeover",
    "ThoughtUnit",
    "Verdict",
    "load_dotenv",
    "parse_steps",
    "run_session",
)

__all__ = list(PUBLIC_API)
