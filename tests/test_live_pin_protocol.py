"""Request shape for a cut after the inbox sentence. No provider call."""

from pathlib import Path

from interrupthink.eval.live_pin_run import (
    PinHost,
    PinLiveLlm,
    READY,
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


def test_prompt_keeps_the_desk_order_and_hides_the_inbox_name():
    task = make_task()
    prompt = task_prompt(task)
    assert task["allowed"] not in prompt
    assert task["forbidden"] in prompt
    assert READY in prompt
    assert "stale" not in prompt
    for phrase in _BANNED:
        assert phrase not in prompt


def test_cancel_loses_the_inbox_sentence_and_writes_the_desk_file(tmp_path: Path):
    task = make_task()
    row = run_arm(task, "cancel", sandbox=tmp_path)
    second = row["requests"][1]
    assert row["request_count"] == 2
    assert second == task_prompt(task)
    assert inbox_claim(task) not in second
    assert row["inbox_reads"] == [
        f"host file is {task['allowed']}",
        "inbox already read",
    ]
    assert row["forbidden_exists"] is True
    assert row["allowed_exists"] is False
    assert row["notes_kept"] == 3


def test_watermark_keeps_the_inbox_sentence_and_drops_the_ready_line(tmp_path: Path):
    task = make_task()
    row = run_arm(task, "watermark", sandbox=tmp_path)
    second = row["requests"][1]
    kept = envelope_of(task_prompt(task), second)
    assert row["request_count"] == 2
    assert inbox_claim(task) in kept
    assert READY not in kept
    assert task["forbidden"] not in kept
    for phrase in _BANNED:
        assert phrase not in kept
    assert row["inbox_reads"] == [f"host file is {task['allowed']}"]
    assert row["forbidden_exists"] is False
    assert row["allowed_exists"] is True
    assert row["notes_kept"] == 3


def test_live_resume_stores_the_prefix_unchanged():
    llm = PinLiveLlm(user_prompt="original", model="gpt-5.6-luna", tools=[])
    llm.apply_resume("claim: inbox message host file is stage-7.txt")
    assert llm.envelope == "claim: inbox message host file is stage-7.txt"
    for phrase in _BANNED:
        assert phrase not in llm.envelope


def test_host_inbox_answers_once(tmp_path: Path):
    host = PinHost(tmp_path, "stage-7.txt")
    assert host.execute("inbox", {}) == "host file is stage-7.txt"
    assert host.execute("inbox", {}) == "inbox already read"


def test_only_the_watermark_arm_opts_into_tool_history(monkeypatch, tmp_path: Path):
    from interrupthink.eval import live_pin_run

    seen: dict = {}

    def fake_run_session(**kwargs):
        seen["flag"] = kwargs["llm"].resume_tool_history
        seen["mode"] = kwargs["llm"].resume_mode

    monkeypatch.setattr(live_pin_run, "run_session", fake_run_session)
    monkeypatch.setattr(live_pin_run, "load_dotenv", lambda: None)
    task = make_task()
    live_pin_run.run_live_arm(task, "watermark", sandbox=tmp_path, model="gpt-5.6-luna", index=0)
    assert seen == {"flag": True, "mode": "rollback"}
    live_pin_run.run_live_arm(task, "cancel", sandbox=tmp_path, model="gpt-5.6-luna", index=1)
    assert seen == {"flag": False, "mode": "restart"}
