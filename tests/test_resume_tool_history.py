"""Resume input keeps executed tool results. No provider call."""

from pathlib import Path

from interrupthink.eval.live_pin_run import (
    PinHost,
    PinLlm,
    READY,
    empty_patch,
    first_document,
    inbox_claim,
    make_task,
    task_prompt,
    watermark_second_document,
)
from interrupthink.monitor.scripted import ScriptedMonitor
from interrupthink.providers.live import LiveLlm
from interrupthink.runtime.session import run_session

_BANNED = (
    "corrected premise",
    "do not plan them again",
    "use the inbox message",
)


class HistoryLlm(PinLlm):
    """Scripted specialist that records the opt-in resume input."""

    resume_tool_history = True

    def __init__(self, documents: list[str], user_prompt: str, *, resume_mode: str) -> None:
        super().__init__(documents, user_prompt, resume_mode=resume_mode)
        self.history: list[dict] | None = None

    def accept_tool_history(self, items: list[dict] | None) -> None:
        self.history = None if items is None else list(items)


def _run(task: dict, arm: str, root: Path) -> HistoryLlm:
    prompt = task_prompt(task)
    second = watermark_second_document(task)
    llm = HistoryLlm(
        [first_document(task), second],
        prompt,
        resume_mode="restart" if arm == "cancel" else "rollback",
    )
    monitor = ScriptedMonitor(
        trigger_kinds=("claim",),
        trigger_contains=READY,
        patch=empty_patch(),
    )
    run_session(llm=llm, monitor=monitor, tool=PinHost(root, task["allowed"]))
    return llm


def _tail(content: str) -> str:
    marker = "Resume prefix (do not repeat dropped text):\n"
    return content.split(marker, 1)[1]


def test_watermark_history_keeps_tool_results_and_drops_the_tail(tmp_path: Path):
    task = make_task()
    llm = _run(task, "watermark", tmp_path)
    items = llm.history or []
    assert items[0]["role"] == "user"
    assert task_prompt(task) in items[0]["content"]
    assert READY not in _tail(items[0]["content"])
    assert task["forbidden"] not in _tail(items[0]["content"])
    calls = [item for item in items if item.get("type") == "function_call"]
    outputs = [item for item in items if item.get("type") == "function_call_output"]
    assert [item["name"] for item in calls] == ["write", "write", "write", "inbox"]
    assert [item["output"] for item in outputs] == [
        "wrote note-0-0.txt",
        "wrote note-0-1.txt",
        "wrote note-0-2.txt",
        f"host file is {task['allowed']}",
    ]
    assert calls[-1]["call_id"] == outputs[-1]["call_id"]
    later = "\n".join(item.get("content", "") for item in items[1:] if "content" in item)
    assert inbox_claim(task) in later
    assert READY not in later
    assert task["forbidden"] not in later
    blob = "\n".join(str(item.get("output", "")) + str(item.get("content", "")) for item in items)
    for phrase in _BANNED:
        assert phrase not in blob
    assert "inbox already read" not in blob


def test_cancel_carries_no_tool_history(tmp_path: Path):
    task = make_task()
    llm = _run(task, "cancel", tmp_path)
    assert llm.history is None
    assert llm.requests[1] == task_prompt(task)


def test_default_live_resume_stays_a_text_prefix():
    llm = LiveLlm(user_prompt="original", model="gpt-5.6-luna", tools=[])
    llm.apply_resume("claim: kept")
    items = llm.initial_transcript()
    assert items == [
        {
            "role": "user",
            "content": "original\n\nResume prefix (do not repeat dropped text):\nclaim: kept",
        }
    ]
    assert llm.resume_tool_history is False
