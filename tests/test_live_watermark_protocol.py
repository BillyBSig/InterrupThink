"""Request shape for a watermark resume. No provider call."""

from pathlib import Path

from interrupthink.eval.live_watermark_run import (
    MARKER,
    WatermarkLiveLlm,
    forbidden_step,
    make_task,
    run_arm,
    task_prompt,
)

_BANNED = (
    "write {allowed} not {forbidden}",
    "do not plan them again",
    "corrected premise",
)


def test_prompt_is_one_document_without_the_marker():
    task = make_task()
    prompt = task_prompt(task)
    assert MARKER not in prompt
    assert forbidden_step(task) not in prompt
    assert task["allowed"] in prompt
    assert task["forbidden"] in prompt
    assert "state the claim that the ticket host is" not in prompt
    for phrase in _BANNED:
        assert phrase not in prompt


def test_cancel_drops_the_accepted_step_and_keeps_files(tmp_path: Path):
    task = make_task()
    row = run_arm(task, "cancel", sandbox=tmp_path)
    assert row["request_count"] == 2
    assert row["requests"][1] == task_prompt(task)
    assert MARKER not in row["requests"][1]
    assert forbidden_step(task) not in row["requests"][1]
    assert row["notes_kept"] == 3
    assert row["forbidden_exists"] is False


def test_watermark_keeps_the_accepted_step_without_a_new_fact(tmp_path: Path):
    task = make_task()
    row = run_arm(task, "watermark", sandbox=tmp_path)
    second = row["requests"][1]
    assert row["request_count"] == 2
    assert MARKER in second
    assert forbidden_step(task) not in second
    for phrase in _BANNED:
        assert phrase not in second
    assert row["notes_kept"] == 3
    assert row["forbidden_exists"] is False


def test_host_policy_denies_the_write_without_a_resume(tmp_path: Path):
    task = make_task()
    row = run_arm(task, "host_policy", sandbox=tmp_path)
    assert row["request_count"] == 1
    assert row["forbidden_exists"] is False
    assert row["notes_kept"] == 3


def test_final_answer_cuts_after_the_forbidden_write(tmp_path: Path):
    task = make_task()
    row = run_arm(task, "final_answer", sandbox=tmp_path)
    assert row["forbidden_exists"] is True
    assert row["request_count"] == 2


def test_live_resume_stores_the_prefix_without_a_new_fact():
    llm = WatermarkLiveLlm(user_prompt="original", model="gpt-5.6-luna", tools=[])
    llm.apply_resume("claim: accepted total is 18")
    assert llm.envelope == "claim: accepted total is 18"
    assert llm.prefix == "claim: accepted total is 18"
    for phrase in _BANNED:
        assert phrase not in llm.envelope


def test_clean_task_stays_one_request(tmp_path: Path):
    task = make_task()
    row = run_arm(task, "clean", sandbox=tmp_path)
    assert row["request_count"] == 1
    assert task["forbidden"] not in row["requests"][0]
    assert row["allowed_exists"] is True
    assert row["forbidden_exists"] is False
    assert row["notes_kept"] == 3
