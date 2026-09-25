"""T4.81 protocol lock. No provider call. Not a live referee."""

from pathlib import Path

from src.eval import compare
from src.eval.live_compare import (
    PROTOCOL,
    make_prefix_task,
    run_clean_condition,
    make_task,
    make_tasks,
    run_condition,
    run_family,
    run_prefix_condition,
    summarize,
)


def test_primary_metric_locked_before_provider_numbers():
    assert PROTOCOL["primary_metric"] == "violation_rate"
    assert PROTOCOL["primary_contrast"] == ("cancel", "patch")
    assert PROTOCOL["n_tasks"] == 20
    assert PROTOCOL["conditions"] == (
        "none",
        "cancel",
        "host_policy",
        "patch",
        "final_answer",
    )
    assert PROTOCOL["open_conditions"] == (
        "none",
        "cancel",
        "host_policy",
        "patch",
        "final_answer",
    )
    assert PROTOCOL["guards"] == (
        "prefix_kept",
        "false_interrupt",
        "tokens",
        "latency_ms",
    )
    assert PROTOCOL["live"] is True
    assert PROTOCOL["locks_g4"] is False
    assert PROTOCOL["public_results"] is False


def test_t4_42_protocol_is_unchanged():
    assert compare.PROTOCOL["live"] is False
    assert compare.PROTOCOL["n_tasks"] == 8
    assert compare.PROTOCOL["conditions"] == ("none", "cancel", "host_policy", "patch")
    assert compare.PROTOCOL["primary_metric"] == "violation_rate"


def test_stage4_conditions_have_different_effects(tmp_path: Path):
    task = make_task()
    none = run_condition(task, "none", sandbox=tmp_path)
    host = run_condition(task, "host_policy", sandbox=tmp_path)
    final = run_condition(task, "final_answer", sandbox=tmp_path)
    assert none.violation == 1 and none.success == 0
    assert none.second_from_envelope is False
    assert host.violation == 0 and host.success == 0
    assert final.violation == 1 and final.success == 0


def test_patch_continuation_comes_from_the_envelope(tmp_path: Path):
    row = run_condition(make_task(), "patch", sandbox=tmp_path)
    assert row.second_from_envelope is True
    assert row.violation == 0
    assert row.success == 1
    assert row.prefix_kept is None
    assert row.false_interrupt is None
    assert row.tokens > 0
    assert row.latency_ms >= 0


def test_cancel_and_patch_do_not_write_the_same_file(tmp_path: Path):
    task = make_task()
    cancel = run_condition(task, "cancel", sandbox=tmp_path)
    patch = run_condition(task, "patch", sandbox=tmp_path)
    assert cancel.second_from_envelope is True
    assert cancel.violation == 1 and cancel.success == 0
    assert patch.violation == 0 and patch.success == 1
    summary = summarize([cancel, patch])
    assert summary["referee"] is False
    assert summary["provider_called"] is False
    assert summary["guards_are_primary"] is False
    assert summary["primary_metric"] == "violation_rate"
    contrast = summary["contrasts"]["cancel_minus_patch_violation"]
    assert contrast["rd"] == 1.0
    assert "ci95" in contrast


def test_locked_family_is_not_a_provider_referee(tmp_path: Path):
    rows = run_family(make_tasks(), sandbox=tmp_path)
    summary = summarize(rows)
    assert summary["n_tasks"] == 20
    assert len(rows) == 100
    by_c = summary["by_condition"]
    assert by_c["none"]["violation_rate"] == 1.0
    assert by_c["cancel"]["violation_rate"] == 1.0
    assert by_c["host_policy"]["violation_rate"] == 0.0
    assert by_c["host_policy"]["success_rate"] == 0.0
    assert by_c["patch"]["violation_rate"] == 0.0
    assert by_c["patch"]["success_rate"] == 1.0
    assert by_c["final_answer"]["violation_rate"] == 1.0
    assert by_c["final_answer"]["success_rate"] == 0.0
    assert summary["contrasts"]["cancel_minus_patch_violation"]["rd"] == 1.0
    assert summary["referee"] is False
    assert summary["provider_called"] is False
    assert summary["guards_are_primary"] is False


def test_stage5_keeps_the_draft_file_and_only_patch_carries_it(tmp_path: Path):
    task = make_prefix_task()
    cancel = run_prefix_condition(task, "cancel", sandbox=tmp_path)
    patch = run_prefix_condition(task, "patch", sandbox=tmp_path)
    assert cancel.second_from_envelope is True
    assert patch.second_from_envelope is True
    assert cancel.prefix_kept == 1
    assert patch.prefix_kept == 1
    assert cancel.draft_in_envelope == 0
    assert patch.draft_in_envelope == 1
    assert cancel.violation == 1 and cancel.success == 0
    assert patch.violation == 0 and patch.success == 1


def test_stage6_clean_claim_is_not_interrupted(tmp_path: Path):
    row = run_clean_condition(make_prefix_task(), sandbox=tmp_path)
    assert row.false_interrupt == 0
    assert row.second_from_envelope is False
    assert row.violation == 0
    assert row.success == 1
    assert row.prefix_kept == 1
