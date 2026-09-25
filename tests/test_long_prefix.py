"""Longer prefix without a provider call. One model only."""

from pathlib import Path

from interrupthink.eval import compare
from interrupthink.eval import live_compare
from interrupthink.eval.long_prefix import PROTOCOL, make_task, run_condition


def test_long_prefix_does_not_change_earlier_protocols():
    assert PROTOCOL["primary_metric"] == "violation_rate"
    assert PROTOCOL["n_drafts"] == 3
    assert PROTOCOL["second_model"] is False
    assert PROTOCOL["locks_g4"] is False
    assert live_compare.PROTOCOL["n_tasks"] == 20
    assert live_compare.PROTOCOL["primary_metric"] == "violation_rate"
    assert compare.PROTOCOL["n_tasks"] == 8
    assert compare.PROTOCOL["live"] is False


def test_three_drafts_remain_and_only_patch_carries_them(tmp_path: Path):
    task = make_task()
    cancel = run_condition(task, "cancel", sandbox=tmp_path)
    patch = run_condition(task, "patch", sandbox=tmp_path)
    assert cancel.second_from_envelope is True
    assert patch.second_from_envelope is True
    assert cancel.prefix_kept == 3
    assert patch.prefix_kept == 3
    assert cancel.drafts_in_envelope == 0
    assert patch.drafts_in_envelope == 3
    assert cancel.violation == 1 and cancel.success == 0
    assert patch.violation == 0 and patch.success == 1
