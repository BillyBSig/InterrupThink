"""G1 lab paths (happy / interrupt / tool). Not library floor."""

from __future__ import annotations

from src.eval.osaka_trap import uses_public_spike_as_demand
from src.eval.scenario import interrupt_restart_prompt, resume_llm_prompt
from src.monitor.base import Monitor
from src.monitor.scripted import ScriptedMonitor
from src.providers.base import Llm
from src.providers.fake import DummyTool, FakeLlm
from src.providers.live import LiveLlm
from src.runtime.events import Patch
from src.runtime.log import JsonlLogger
from src.runtime.session import SpikeResult, _run_session

HAPPY_XML = """
<step kind="plan">outline the FY revenue claim</step>
<step kind="premise">use the rolling FY baseline</step>
<step kind="claim">revenue is up versus the rolling FY baseline</step>
<answer>Revenue rose against the rolling FY baseline.</answer>
"""

INTERRUPT_XML_1 = """
<step kind="plan">outline the FY revenue claim</step>
<step kind="premise">Q3 Japan is the annual trend</step>
<step kind="claim">therefore the year is a boom</step>
<step kind="evidence">this tail must be dropped</step>
"""

INTERRUPT_XML_2 = """
<step kind="claim">revenue is mixed once Q3 is treated as an anomaly</step>
<answer>Do not treat Q3 Japan as the annual trend.</answer>
"""

TOOL_XML = """
<step kind="plan">fetch the baseline before claiming</step>
<step kind="tool_intent" reversible="false">{"name":"fetch_baseline","args":{"window":"FY"}}</step>
<step kind="claim">baseline fetched</step>
<answer>Baseline is ready.</answer>
"""

G1_HAPPY_USER_PROMPT = """Berdasarkan fakta berikut, sebut ibu kota Prancis dan satu kalimat mengapa itu relevan untuk kantor EMEA fiktif.

Fakta: Paris adalah ibu kota Prancis; kantor EMEA fiktif butuh zona waktu dekat klien Prancis."""


def g1_live_interrupt_monitor() -> ScriptedMonitor:
    return ScriptedMonitor(
        trigger_kind=None,
        trigger_kinds=("premise", "claim"),
        trigger_contains="Q3",
        patch=Patch(
            from_agent="A",
            target_unit_id="",
            rollback_to=None,
            diagnosis="Q3 dipakai sebagai tren tahunan",
            missing="Q3 anomali; FY rolling -4%; kebijakan FY",
            directive="ulang dari plan dengan baseline FY rolling, bukan Q3",
            preserve=[],
        ),
    )


def _lab_session(
    path: str,
    llm: Llm,
    monitor: Monitor,
    tool: DummyTool,
    logger: JsonlLogger,
) -> SpikeResult:
    return _run_session(
        path,
        llm,
        monitor,
        tool,
        logger,
        execute_tools_when_ok=True,
        rewrite_kept=uses_public_spike_as_demand,
        lab_restart_prompt=interrupt_restart_prompt,
        lab_resume_prompt=resume_llm_prompt,
    )


def run_path(
    path: str,
    *,
    logger: JsonlLogger | None = None,
    llm: Llm | None = None,
    monitor: Monitor | None = None,
    tool: DummyTool | None = None,
) -> SpikeResult:
    logger = logger or JsonlLogger()
    tool = tool or DummyTool()
    if path == "happy":
        llm = llm or FakeLlm([HAPPY_XML])
        monitor = monitor or ScriptedMonitor(trigger_kind=None)
        return _lab_session(path, llm, monitor, tool, logger)
    if path == "interrupt":
        llm = llm or FakeLlm([INTERRUPT_XML_1, INTERRUPT_XML_2])
        if monitor is None:
            if isinstance(llm, LiveLlm):
                monitor = g1_live_interrupt_monitor()
            else:
                monitor = ScriptedMonitor(
                    trigger_kind="premise",
                    trigger_contains="Q3 Japan",
                )
        return _lab_session(path, llm, monitor, tool, logger)
    if path == "tool":
        llm = llm or FakeLlm([TOOL_XML])
        monitor = monitor or ScriptedMonitor(
            trigger_kind=None,
            hold_irreversible_tool=True,
        )
        return _lab_session(path, llm, monitor, tool, logger)
    raise ValueError(f"unknown path: {path}")
