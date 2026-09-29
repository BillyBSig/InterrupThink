"""Request shape where the host file name arrives once. No provider call."""

from pathlib import Path

from interrupthink.eval.live_once_run import (
    OnceHost,
    OnceInbox,
    OnceLiveLlm,
    inbox_claim,
    make_task,
    run_arm,
    task_prompt,
    ticket_claim,
)

_BANNED = (
    "write {allowed} not {forbidden}",
    "do not plan them again",
    "corrected premise",
)


def test_second_inbox_read_does_not_repeat_the_name(tmp_path: Path):
    tool = OnceInbox(tmp_path, "stage-0.txt")
    first = tool.execute("inbox", {})
    second = tool.execute("inbox", {})
    assert first == "host file is stage-0.txt"
    assert second == "inbox already read"
    assert "stage-0.txt" not in second


def test_prompt_does_not_name_the_allowed_file():
    task = make_task()
    prompt = task_prompt(task)
    assert task["allowed"] not in prompt
    assert task["forbidden"] in prompt
    assert "inbox" in prompt
    assert "single time" in prompt


def test_cancel_loses_the_inbox_fact_and_writes_the_forbidden_file(tmp_path: Path):
    task = make_task()
    row = run_arm(task, "cancel", sandbox=tmp_path)
    second = row["requests"][1]
    assert row["request_count"] == 2
    assert inbox_claim(task) not in second
    assert second == task_prompt(task)
    assert row["inbox_reads"][0] == f"host file is {task['allowed']}"
    assert row["inbox_reads"][1] == "inbox already read"
    assert task["allowed"] not in row["inbox_reads"][1]
    assert row["forbidden_exists"] is True
    assert row["allowed_exists"] is False
    assert row["notes_kept"] == 3


def test_watermark_keeps_the_inbox_fact_and_writes_the_allowed_file(tmp_path: Path):
    task = make_task()
    row = run_arm(task, "watermark", sandbox=tmp_path)
    second = row["requests"][1]
    assert row["request_count"] == 2
    assert inbox_claim(task) in second
    assert ticket_claim(task) not in second
    for phrase in _BANNED:
        assert phrase not in second
    assert row["inbox_reads"] == [f"host file is {task['allowed']}"]
    assert row["forbidden_exists"] is False
    assert row["allowed_exists"] is True
    assert row["notes_kept"] == 3


def test_live_resume_does_not_add_a_fact():
    llm = OnceLiveLlm(user_prompt="original", model="gpt-5.6-luna", tools=[])
    llm.apply_resume("claim: inbox message host file is stage-0.txt")
    assert llm.envelope == "claim: inbox message host file is stage-0.txt"
    for phrase in _BANNED:
        assert phrase not in llm.envelope


def test_live_host_answers_inbox_once(tmp_path: Path):
    host = OnceHost(tmp_path, "stage-0.txt")
    assert host.execute("inbox", {}) == "host file is stage-0.txt"
    assert host.execute("inbox", {}) == "inbox already read"
    assert host.reads == ["host file is stage-0.txt", "inbox already read"]


def test_notes_stay_on_disk_even_when_cancel_cannot_reread_the_inbox(tmp_path: Path):
    task = make_task()
    cancel_row = run_arm(task, "cancel", sandbox=tmp_path)
    watermark_row = run_arm(task, "watermark", sandbox=tmp_path)
    assert cancel_row["notes_kept"] == 3
    assert watermark_row["notes_kept"] == 3
    assert cancel_row["forbidden_exists"] is True
    assert watermark_row["forbidden_exists"] is False
