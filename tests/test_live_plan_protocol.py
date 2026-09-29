"""Request shape when two plan lines stay after a cut. No provider call."""

from pathlib import Path

from interrupthink.eval.live_plan_run import (
    PLAN_LATER,
    PLAN_NEXT,
    PlanHost,
    envelope_of,
    inbox_claim,
    make_task,
    run_arm,
    task_prompt,
)

_BANNED = (
    "write {allowed} not {forbidden}",
    "do not plan them again",
    "corrected premise",
    "use the inbox message",
    "if it disagrees",
)


def test_prompt_hides_every_host_file_name():
    for index in (0, 4):
        task = make_task(index)
        prompt = task_prompt(task)
        assert task["allowed"] not in prompt
        assert task["forbidden"] not in prompt
        assert task["close"] not in prompt
        assert "stage-" not in prompt
        assert "prod-" not in prompt
        assert "close-" not in prompt
        assert "stale" not in prompt
        assert "desk order" not in prompt
        assert PLAN_NEXT in prompt
        assert PLAN_LATER in prompt
        for phrase in _BANNED:
            assert phrase not in prompt


def test_cancel_returns_to_the_prompt_and_writes_only_notes(tmp_path: Path):
    task = make_task()
    row = run_arm(task, "cancel", sandbox=tmp_path)
    second = row["requests"][1]
    assert row["request_count"] == 2
    assert second == task_prompt(task)
    assert inbox_claim(task) not in second
    assert task["allowed"] not in second
    assert row["inbox_reads"] == [
        f"host file is {task['allowed']}",
        "inbox already read",
    ]
    assert row["notes_kept"] == 3
    assert row["allowed_exists"] is False
    assert row["close_exists"] is False
    assert row["forbidden_exists"] is False
    assert row["files"] == list(task["notes"])


def test_watermark_keeps_the_later_plan_and_writes_the_close_note(tmp_path: Path):
    task = make_task(7)
    row = run_arm(task, "watermark", sandbox=tmp_path)
    second = row["requests"][1]
    kept = envelope_of(task_prompt(task), second)
    assert row["request_count"] == 2
    assert inbox_claim(task) in kept
    assert f"plan: {PLAN_NEXT}" in kept
    assert f"plan: {PLAN_LATER}" in kept
    assert kept.index(inbox_claim(task)) < kept.index(PLAN_NEXT) < kept.index(PLAN_LATER)
    assert task["forbidden"] not in kept
    assert task["forbidden"] not in second
    for phrase in _BANNED:
        assert phrase not in kept
    assert row["inbox_reads"] == [f"host file is {task['allowed']}"]
    assert row["notes_kept"] == 3
    assert row["allowed_exists"] is True
    assert row["close_exists"] is True
    assert row["close_text"] == task["allowed"]
    assert row["forbidden_exists"] is False
    assert set(row["files"]) == set(task["notes"]) | {task["allowed"], task["close"]}


def test_host_inbox_answers_once(tmp_path: Path):
    host = PlanHost(tmp_path, "stage-7.txt")
    assert host.execute("inbox", {}) == "host file is stage-7.txt"
    assert host.execute("inbox", {}) == "inbox already read"


def test_live_resume_stores_the_prefix_unchanged():
    from interrupthink.eval.live_plan_run import PlanLiveLlm

    llm = PlanLiveLlm(user_prompt="original", model="gpt-5.6-luna", tools=[])
    llm.apply_resume("plan: following plan: write a close note that repeats the inbox host file name")
    assert "stage-" not in llm.envelope
    assert llm.resume_tool_history is False
    for phrase in _BANNED:
        assert phrase not in llm.envelope


def test_carried_history_keeps_inbox_result_and_the_later_plan(tmp_path: Path):
    from interrupthink.eval.live_plan_run import (
        PlanHost,
        PlanLlm,
        cancel_second_document,
        empty_patch,
        first_document,
        watermark_second_document,
    )
    from interrupthink.monitor.scripted import ScriptedMonitor
    from interrupthink.runtime.session import run_session

    class HistoryPlanLlm(PlanLlm):
        resume_tool_history = True

        def __init__(self, documents: list[str], user_prompt: str, *, resume_mode: str) -> None:
            super().__init__(documents, user_prompt, resume_mode=resume_mode)
            self.history: list[dict] | None = None

        def accept_tool_history(self, items: list[dict] | None) -> None:
            self.history = None if items is None else list(items)

    task = make_task(3)
    prompt = task_prompt(task)

    def run(arm: str) -> HistoryPlanLlm:
        second = cancel_second_document(task) if arm == "cancel" else watermark_second_document(task)
        llm = HistoryPlanLlm(
            [first_document(task), second],
            prompt,
            resume_mode="restart" if arm == "cancel" else "rollback",
        )
        run_session(
            llm=llm,
            monitor=ScriptedMonitor(
                trigger_kinds=("tool_intent",),
                trigger_contains=task["forbidden"],
                patch=empty_patch(),
            ),
            tool=PlanHost(tmp_path / arm, task["allowed"]),
        )
        return llm

    kept = run("watermark")
    items = kept.history or []
    calls = [item for item in items if item.get("type") == "function_call"]
    outputs = [item for item in items if item.get("type") == "function_call_output"]
    assert [item["name"] for item in calls] == ["write", "write", "write", "inbox"]
    assert [item["output"] for item in outputs] == [
        "wrote note-3-0.txt",
        "wrote note-3-1.txt",
        "wrote note-3-2.txt",
        f"host file is {task['allowed']}",
    ]
    later = "\n".join(item.get("content", "") for item in items if "content" in item)
    assert inbox_claim(task) in later
    assert PLAN_LATER in later
    assert task["forbidden"] not in later
    assert "inbox already read" not in later
    for phrase in _BANNED:
        assert phrase not in later
    assert run("cancel").history is None


def test_only_watermark_can_carry_tool_history(monkeypatch, tmp_path: Path):
    from interrupthink.eval import live_plan_run

    seen: dict = {}

    def fake_run_session(**kwargs):
        seen["flag"] = kwargs["llm"].resume_tool_history
        seen["mode"] = kwargs["llm"].resume_mode

    monkeypatch.setattr(live_plan_run, "run_session", fake_run_session)
    monkeypatch.setattr(live_plan_run, "load_dotenv", lambda: None)
    task = make_task()
    live_plan_run.run_live_arm(
        task, "watermark", sandbox=tmp_path, model="gpt-5.6-luna", index=0, carry_tool_history=True
    )
    assert seen == {"flag": True, "mode": "rollback"}
    live_plan_run.run_live_arm(
        task, "cancel", sandbox=tmp_path, model="gpt-5.6-luna", index=1, carry_tool_history=True
    )
    assert seen == {"flag": False, "mode": "restart"}


def test_live_arms_keep_text_prefix_and_cut_on_the_inbox_file(monkeypatch, tmp_path: Path):
    from interrupthink.eval import live_plan_run

    seen: dict = {}

    def fake_run_session(**kwargs):
        seen["flag"] = kwargs["llm"].resume_tool_history
        seen["mode"] = kwargs["llm"].resume_mode
        seen["rounds"] = kwargs["llm"].max_tool_rounds
        seen["contains"] = kwargs["monitor"].trigger_contains
        seen["kinds"] = kwargs["monitor"].trigger_kinds

    monkeypatch.setattr(live_plan_run, "run_session", fake_run_session)
    monkeypatch.setattr(live_plan_run, "load_dotenv", lambda: None)
    task = make_task()
    live_plan_run.run_live_arm(task, "watermark", sandbox=tmp_path, model="gpt-5.6-luna", index=0)
    assert seen["flag"] is False
    assert seen["mode"] == "rollback"
    assert seen["rounds"] == 8
    assert seen["contains"] == task["allowed"]
    assert seen["kinds"] == ("tool_intent",)
    live_plan_run.run_live_arm(task, "cancel", sandbox=tmp_path, model="gpt-5.6-luna", index=1)
    assert seen["flag"] is False
    assert seen["mode"] == "restart"
