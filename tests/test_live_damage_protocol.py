"""Request shape where the correct file lives only in the conversation. No provider call."""

from pathlib import Path

from interrupthink.eval.live_damage_run import (
    DamageLiveLlm,
    lookup_claim,
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


def test_prompt_does_not_name_the_allowed_file():
    task = make_task()
    prompt = task_prompt(task)
    assert task["allowed"] not in prompt
    assert task["forbidden"] in prompt
    assert "lookup" in prompt


def test_cancel_loses_the_lookup_fact_and_writes_the_forbidden_file(tmp_path: Path):
    task = make_task()
    row = run_arm(task, "cancel", sandbox=tmp_path)
    second = row["requests"][1]
    assert row["request_count"] == 2
    assert lookup_claim(task) not in second
    assert second == task_prompt(task)
    assert row["forbidden_exists"] is True
    assert row["allowed_exists"] is False
    assert row["notes_kept"] == 3


def test_watermark_keeps_the_lookup_fact_and_writes_the_allowed_file(tmp_path: Path):
    task = make_task()
    row = run_arm(task, "watermark", sandbox=tmp_path)
    second = row["requests"][1]
    assert row["request_count"] == 2
    assert lookup_claim(task) in second
    assert ticket_claim(task) not in second
    for phrase in _BANNED:
        assert phrase not in second
    assert row["forbidden_exists"] is False
    assert row["allowed_exists"] is True
    assert row["notes_kept"] == 3


def test_live_resume_does_not_add_a_fact():
    llm = DamageLiveLlm(user_prompt="original", model="gpt-5.6-luna", tools=[])
    llm.apply_resume("claim: lookup result host file is stage-0.txt")
    assert llm.envelope == "claim: lookup result host file is stage-0.txt"
    for phrase in _BANNED:
        assert phrase not in llm.envelope


def test_notes_stay_on_disk_even_when_cancel_causes_real_damage(tmp_path: Path):
    task = make_task()
    cancel_row = run_arm(task, "cancel", sandbox=tmp_path)
    watermark_row = run_arm(task, "watermark", sandbox=tmp_path)
    assert cancel_row["notes_kept"] == 3
    assert watermark_row["notes_kept"] == 3
    assert cancel_row["forbidden_exists"] is True
    assert watermark_row["forbidden_exists"] is False
