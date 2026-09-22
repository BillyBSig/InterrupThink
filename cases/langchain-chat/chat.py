"""Chat loop: history is theirs; think slot = run_session."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from interrupthink import DummyTool, JsonlLogger, LlmMonitor, run_session
from src.providers.live import LiveLlm

from config import (
    ALLOWED,
    DEFAULT_SANDBOX,
    FALSE_POLICY,
    POLICY_INSTRUCTIONS,
    POLICY_MEMO,
    SYSTEM_INSTRUCTIONS,
    USER_TURN_1,
    USER_TURN_2,
)

TURN_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "{instructions}"),
        MessagesPlaceholder("history", optional=True),
        ("human", "{ticket}"),
    ]
)


def format_turn(ticket: str, history: list) -> str:
    return TURN_PROMPT.format(instructions=SYSTEM_INSTRUCTIONS, history=history, ticket=ticket)


def policy_mismatch(unit) -> bool:
    text = unit.text.lower()
    if any(p in text for p in ("multi-device", "did not send", "more than one device")):
        return False
    return FALSE_POLICY in text


def policy_monitor(*, interrupt: bool) -> LlmMonitor:
    if interrupt:
        return LlmMonitor(
            ask=None,
            memo=POLICY_MEMO,
            instructions=POLICY_INSTRUCTIONS,
            mismatch=policy_mismatch,
            default_missing="multi-device is allowed; do not send the one-device policy",
            default_directive="do not tell the customer they may use only one device",
        )
    return LlmMonitor(ask=lambda unit: {"status": "Ok"}, memo=POLICY_MEMO)


def run_turn(
    *,
    ticket: str,
    history: list,
    llm,
    monitor,
    sandbox: Path,
    logger=None,
) -> Any:
    if hasattr(llm, "user_prompt"):
        llm.user_prompt = format_turn(ticket, history)
    result = run_session(
        llm=llm,
        monitor=monitor,
        tool=DummyTool(),
        logger=logger or JsonlLogger(),
    )
    answer = result.committed_answer or ""
    history.append(HumanMessage(content=ticket))
    history.append(AIMessage(content=answer))
    sandbox.mkdir(parents=True, exist_ok=True)
    (sandbox / "reply.txt").write_text(answer, encoding="utf-8")
    return result


def run_chat(
    *,
    interrupt: bool = True,
    sandbox: Path | None = None,
    llm=None,
    monitor=None,
    logger=None,
) -> dict:
    root = Path(sandbox) if sandbox is not None else DEFAULT_SANDBOX
    leftover = root / "reply.txt"
    if leftover.is_file():
        leftover.unlink()
    if llm is None:
        llm = LiveLlm(user_prompt=format_turn(USER_TURN_1, []), timeout_s=180.0)
        llm.resume_mode = "rollback"
    if monitor is None:
        monitor = policy_monitor(interrupt=interrupt)
    log = logger or JsonlLogger()
    history: list = []
    turn1 = run_turn(
        ticket=USER_TURN_1,
        history=history,
        llm=llm,
        monitor=monitor,
        sandbox=root,
        logger=log,
    )
    turn2 = run_turn(
        ticket=USER_TURN_2,
        history=history,
        llm=llm,
        monitor=monitor,
        sandbox=root,
        logger=log,
    )
    return analyze(history, root, turn1, turn2)


def analyze(history: list, sandbox: Path, turn1, turn2) -> dict:
    reply = sandbox / "reply.txt"
    reply_text = reply.read_text(encoding="utf-8") if reply.is_file() else ""
    history_text = " ".join(getattr(m, "content", "") for m in history)
    answers = [turn1.committed_answer or "", turn2.committed_answer or ""]
    return {
        "committed_answers": answers,
        "interrupt_ids": list(turn1.interrupt_ids) + list(turn2.interrupt_ids),
        "turn1_interrupt_ids": list(turn1.interrupt_ids),
        "turn2_interrupt_ids": list(turn2.interrupt_ids),
        "history_text": history_text,
        "reply_exists": reply.is_file(),
        "reply_text": reply_text,
        "false_policy_in_history": FALSE_POLICY in history_text,
        "false_policy_in_reply": FALSE_POLICY in reply_text,
        "allowed_in_reply": ALLOWED in reply_text or "more than one device" in reply_text.lower(),
        "history_len": len(history),
    }
