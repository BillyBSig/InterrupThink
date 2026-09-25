"""Four-condition protected-write protocol. Dummy FakeLlm. No API key. Not Osaka."""

from pathlib import Path

from interrupthink.eval import compare


def test_primary_metric_locked_before_numbers():
    assert compare.PROTOCOL["primary_metric"] == "violation_rate"
    assert compare.PROTOCOL["primary_contrast"] == ("cancel", "patch")
    assert compare.PROTOCOL["n_tasks"] == 8
    assert compare.PROTOCOL["live"] is False
    assert compare.PROTOCOL["locks_g4"] is False
    assert compare.CONDITIONS == ("none", "cancel", "host_policy", "patch")


def test_compare_module_is_not_trap_rescoring():
    text = Path(compare.__file__).read_text(encoding="utf-8")
    assert "score_p1" not in text
    assert "run_path" not in text
    assert "osaka_trap" not in text
    assert "run_c0" not in text
    assert "run_c1" not in text


def test_four_conditions_one_task(tmp_path: Path):
    task = compare.make_tasks(1)[0]
    none = compare.run_condition(task, "none", sandbox=tmp_path)
    cancel = compare.run_condition(task, "cancel", sandbox=tmp_path)
    host = compare.run_condition(task, "host_policy", sandbox=tmp_path)
    patch = compare.run_condition(task, "patch", sandbox=tmp_path)
    assert none.violation == 1 and none.success == 0
    assert cancel.violation == 1 and cancel.success == 0
    assert host.violation == 0 and host.success == 0
    assert patch.violation == 0 and patch.success == 1


def test_family_reports_effect_size_not_single_pass(tmp_path: Path):
    rows = compare.run_family(compare.make_tasks(), sandbox=tmp_path)
    summary = compare.summarize(rows)
    assert summary["n_tasks"] == 8
    assert summary["primary_metric"] == "violation_rate"
    by_c = summary["by_condition"]
    assert by_c["none"]["violation_rate"] == 1.0
    assert by_c["cancel"]["violation_rate"] == 1.0
    assert by_c["host_policy"]["violation_rate"] == 0.0
    assert by_c["patch"]["violation_rate"] == 0.0
    assert by_c["patch"]["success_rate"] == 1.0
    assert by_c["cancel"]["success_rate"] == 0.0
    rd = summary["contrasts"]["cancel_minus_patch_violation"]
    assert rd["rd"] == 1.0
    assert "ci95" in rd and len(rd["ci95"]) == 2
    assert by_c["none"]["violation_ci95"][0] <= by_c["none"]["violation_ci95"][1]
    assert summary["protocol_ok"] is True
    assert summary["locks_g4"] is False
