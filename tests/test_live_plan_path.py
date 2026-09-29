"""Request shape when the second plan step is its own file. No provider call."""

from pathlib import Path

from interrupthink.eval.live_plan_path_run import (
    disk_score,
    inbox_claim,
    make_task,
    run_arm,
    task_prompt,
)
from interrupthink.eval.live_plan_run import PLAN_NEXT

_BANNED = (
    "write {allowed} not {forbidden}",
    "do not plan them again",
    "corrected premise",
    "use the inbox message",
    "if it disagrees",
)


def test_prompt_names_the_close_file_and_hides_the_host_name():
    task = make_task(2)
    prompt = task_prompt(task)
    assert task["close"] in prompt
    assert task["allowed"] not in prompt
    assert task["forbidden"] not in prompt
    assert "stage-" not in prompt
    assert "prod-" not in prompt
    assert PLAN_NEXT in prompt
    assert task["plan_later"] in prompt
    assert "stale" not in prompt
    for phrase in _BANNED:
        assert phrase not in prompt


def test_cancel_does_not_write_the_close_file(tmp_path: Path):
    task = make_task()
    row = run_arm(task, "cancel", sandbox=tmp_path)
    assert row["request_count"] == 2
    assert row["requests"][1] == task_prompt(task)
    assert inbox_claim(task) not in row["requests"][1]
    assert row["inbox_reads"] == [
        f"host file is {task['allowed']}",
        "inbox already read",
    ]
    assert row["notes_kept"] == 3
    assert row["allowed_exists"] is False
    assert row["close_exists"] is False
    assert row["close_exact"] is False
    assert row["forbidden_exists"] is False


def test_watermark_writes_the_close_file_with_only_the_host_name(tmp_path: Path):
    task = make_task(5)
    row = run_arm(task, "watermark", sandbox=tmp_path)
    second = row["requests"][1]
    assert row["request_count"] == 2
    assert inbox_claim(task) in second
    assert task["plan_later"] in second
    assert task["forbidden"] not in second
    for phrase in _BANNED:
        assert phrase not in second
    assert row["inbox_reads"] == [f"host file is {task['allowed']}"]
    assert row["notes_kept"] == 3
    assert row["allowed_exists"] is True
    assert row["close_exact"] is True
    assert row["forbidden_exists"] is False


def test_host_file_body_does_not_count_as_the_close_file(tmp_path: Path):
    task = make_task(1)
    root = tmp_path / "only-host"
    root.mkdir()
    (root / task["allowed"]).write_text(task["plan_later"] + " " + task["allowed"], encoding="utf-8")
    for note in task["notes"]:
        (root / note).write_text("note", encoding="utf-8")
    scored = disk_score(root, task)
    assert scored["allowed_exists"] is True
    assert scored["close_exists"] is False
    assert scored["close_exact"] is False


def test_carried_history_keeps_the_inbox_name_and_the_close_path(tmp_path: Path):
    from interrupthink.eval.live_plan_path_run import (
        cancel_second_document,
        first_document,
        watermark_second_document,
    )
    from interrupthink.eval.live_plan_run import PlanHost, PlanLlm, empty_patch
    from interrupthink.monitor.scripted import ScriptedMonitor
    from interrupthink.runtime.session import run_session

    class HistoryLlm(PlanLlm):
        resume_tool_history = True

        def __init__(self, documents: list[str], user_prompt: str, *, resume_mode: str) -> None:
            super().__init__(documents, user_prompt, resume_mode=resume_mode)
            self.history: list[dict] | None = None

        def accept_tool_history(self, items: list[dict] | None) -> None:
            self.history = None if items is None else list(items)

    task = make_task(3)
    prompt = task_prompt(task)
    llm = HistoryLlm(
        [first_document(task), watermark_second_document(task)],
        prompt,
        resume_mode="rollback",
    )
    run_session(
        llm=llm,
        monitor=ScriptedMonitor(
            trigger_kinds=("tool_intent",),
            trigger_contains=task["allowed"],
            patch=empty_patch(),
        ),
        tool=PlanHost(tmp_path / "watermark", task["allowed"]),
    )
    items = llm.history or []
    outputs = [item["output"] for item in items if item.get("type") == "function_call_output"]
    assert outputs[-1] == f"host file is {task['allowed']}"
    later = "\n".join(item.get("content", "") for item in items if "content" in item)
    assert task["plan_later"] in later
    assert task["close"] in later
    assert "inbox already read" not in later
    cancel = HistoryLlm(
        [first_document(task), cancel_second_document(task)],
        prompt,
        resume_mode="restart",
    )
    run_session(
        llm=cancel,
        monitor=ScriptedMonitor(
            trigger_kinds=("tool_intent",),
            trigger_contains=task["allowed"],
            patch=empty_patch(),
        ),
        tool=PlanHost(tmp_path / "cancel", task["allowed"]),
    )
    assert cancel.history is None


def test_host_policy_denies_only_the_forbidden_write(tmp_path: Path):
    from interrupthink.eval.live_plan_path_run import arm_controls

    task = make_task(6)
    prompt = task_prompt(task)
    assert task["allowed"] not in prompt
    assert task["forbidden"] not in prompt
    monitor, policy = arm_controls(task, "host_policy")
    assert monitor.trigger_kind is None
    assert monitor.trigger_contains is None
    assert monitor.patch.missing == ""
    assert monitor.patch.directive == ""
    assert policy("write", {"path": task["forbidden"]}) is False
    assert policy("write", {"path": f"desk/{task['forbidden']}"}) is False
    assert policy("write", {"path": task["allowed"]}) is True
    assert policy("write", {"path": task["close"]}) is True
    assert policy("write", {"path": task["notes"][0]}) is True
    assert policy("inbox", {}) is True
    row = run_arm(task, "host_policy", sandbox=tmp_path)
    assert row["request_count"] == 1
    assert row["notes_kept"] == 3
    assert row["allowed_exists"] is True
    assert row["close_exact"] is True
    assert row["forbidden_exists"] is False
    for phrase in _BANNED:
        assert phrase not in row["requests"][0]


def test_final_answer_restarts_from_the_prompt_after_the_answer(tmp_path: Path):
    from interrupthink.eval.live_plan_path_run import arm_controls, final_answer_document

    task = make_task(8)
    monitor, policy = arm_controls(task, "final_answer")
    assert policy is None
    assert monitor.trigger_kind == "answer_draft"
    assert monitor.trigger_kinds is None
    assert monitor.trigger_contains == task["forbidden"]
    assert task["allowed"] not in (monitor.trigger_contains or "")
    assert monitor.patch.missing == ""
    assert monitor.patch.directive == ""
    assert task["allowed"] in final_answer_document(task)
    assert f"answer: Wrote {task['forbidden']}." in final_answer_document(task)
    row = run_arm(task, "final_answer", sandbox=tmp_path)
    assert row["request_count"] == 2
    assert row["requests"][1] == task_prompt(task)
    assert row["allowed_exists"] is True
    assert row["close_exact"] is True
    for phrase in _BANNED:
        assert phrase not in row["requests"][1]


def test_baselines_do_not_carry_tool_history(monkeypatch, tmp_path: Path):
    from interrupthink.eval import live_plan_path_run

    seen: dict = {}

    def fake_run_session(**kwargs):
        seen["flag"] = kwargs["llm"].resume_tool_history
        seen["mode"] = kwargs["llm"].resume_mode
        seen["kind"] = kwargs["monitor"].trigger_kind
        seen["contains"] = kwargs["monitor"].trigger_contains
        seen["missing"] = kwargs["monitor"].patch.missing
        seen["policy"] = kwargs["tool_policy"]

    monkeypatch.setattr(live_plan_path_run, "run_session", fake_run_session)
    monkeypatch.setattr(live_plan_path_run, "load_dotenv", lambda: None)
    task = make_task()
    live_plan_path_run.run_live_arm(
        task,
        "host_policy",
        sandbox=tmp_path,
        model="gpt-5.6-terra",
        index=0,
        carry_tool_history=True,
    )
    assert seen["flag"] is False
    assert seen["mode"] == "restart"
    assert seen["kind"] is None
    assert seen["missing"] == ""
    assert seen["policy"]("write", {"path": task["forbidden"]}) is False
    assert seen["policy"]("write", {"path": task["allowed"]}) is True
    live_plan_path_run.run_live_arm(
        task,
        "final_answer",
        sandbox=tmp_path,
        model="gpt-5.6-terra",
        index=1,
        carry_tool_history=True,
    )
    assert seen["flag"] is False
    assert seen["mode"] == "restart"
    assert seen["kind"] == "answer_draft"
    assert seen["contains"] == task["forbidden"]
    assert seen["missing"] == ""
    assert seen["policy"] is None


def test_only_watermark_carries_tool_history(monkeypatch, tmp_path: Path):
    from interrupthink.eval import live_plan_path_run

    seen: dict = {}

    def fake_run_session(**kwargs):
        seen["flag"] = kwargs["llm"].resume_tool_history
        seen["mode"] = kwargs["llm"].resume_mode
        seen["contains"] = kwargs["monitor"].trigger_contains

    monkeypatch.setattr(live_plan_path_run, "run_session", fake_run_session)
    monkeypatch.setattr(live_plan_path_run, "load_dotenv", lambda: None)
    task = make_task()
    live_plan_path_run.run_live_arm(
        task, "watermark", sandbox=tmp_path, model="gpt-5.6-terra", index=0, carry_tool_history=True
    )
    assert seen["flag"] is True
    assert seen["mode"] == "rollback"
    assert seen["contains"] == task["allowed"]
    live_plan_path_run.run_live_arm(
        task, "cancel", sandbox=tmp_path, model="gpt-5.6-terra", index=1, carry_tool_history=True
    )
    assert seen["flag"] is False
    assert seen["mode"] == "restart"
