"""Live-monitor measurement protocol. Mocked HTTP. No API key. Does not lock G4."""

from pathlib import Path

from interrupthink.eval import measure


def test_primary_metric_locked_before_numbers():
    assert measure.PROTOCOL["primary_metric"] == "trace_complete"
    assert measure.PROTOCOL["n_max"] == 3
    assert measure.PROTOCOL["conditions"] == ("ok", "timeout", "cancel")
    assert measure.PROTOCOL["locks_g4"] is False
    assert measure.PROTOCOL["public_results"] is False
    assert measure.PROTOCOL["family_live"] is True
    assert "live" not in measure.PROTOCOL
    assert "executed_live" not in measure.PROTOCOL


def test_measure_module_is_not_public_or_t42():
    text = Path(measure.__file__).read_text(encoding="utf-8")
    assert "score_p1" not in text
    assert "osaka_trap" not in text
    assert "violation_rate" not in text
    assert "docs/results.md" not in text


def test_mock_family_traces_are_complete():
    def complete_ok(*, model: str):
        return '{"status":"Ok"}', {"input_tokens": 11, "output_tokens": 7}

    rows = measure.run_family(
        complete_ok=complete_ok,
        complete_timeout=None,
        abort=lambda: True,
    )
    summary = measure.summarize(rows)
    assert summary["n"] == 3
    assert summary["trace_complete"] == 1.0
    assert summary["protocol_ok"] is True
    assert summary["locks_g4"] is False
    assert summary["public_results"] is False
    assert summary["family_live"] is True
    assert summary["executed_live"] is False
    assert "live" not in summary
    by = summary["by_condition"]
    assert by["ok"]["timeout"] is False
    assert by["ok"]["output_tokens"] == 7
    assert by["timeout"]["timeout"] is True
    assert by["timeout"]["failure_category"] == "timeout"
    assert by["cancel"]["cancel_ok"] is True
    assert by["ok"]["latency_ms"] >= 0
    assert by["timeout"]["latency_ms"] >= 0
    assert by["cancel"]["latency_ms"] >= 0


def test_summarize_can_mark_executed_live():
    rows = measure.run_family()
    summary = measure.summarize(rows, executed_live=True)
    assert summary["family_live"] is True
    assert summary["executed_live"] is True
    assert "live" not in summary
