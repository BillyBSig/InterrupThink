import pytest

from pathlib import Path

from interrupthink.cli.eval import main
from interrupthink.eval.runner import run_c1
from interrupthink.eval.summary import evaluate_gates
from interrupthink.eval.types import TrialResult


def test_eval_cli_imports_the_eval_package():
    source = Path(__file__).resolve().parents[1] / "src" / "interrupthink" / "cli" / "eval.py"
    body = source.read_text(encoding="utf-8")
    assert "from interrupthink.eval" in body
    assert "from interrupthink import run_path" not in body
    assert "interrupthink.run_path" not in body


def test_cli_stub_exits_zero(capsys):
    assert main(["--stub", "--pairs", "1"]) == 0
    out = capsys.readouterr().out
    assert "proposal" in out


def test_cli_rejects_unknown_ablation():
    with pytest.raises(SystemExit):
        main(["--ablation", "nope", "--stub"])


def test_a31_stub_c1_is_filter_path():
    trial = run_c1(seed="stub-a31")
    assert trial.condition == "C1"
    assert trial.interrupts_used >= 1


def test_evaluate_gates_c1_vs_a31_labels():
    pairs = [
        (
            TrialResult("C1", "s0", "ans", 1, 1, 100, 10.0),
            TrialResult("A3.1", "s0", "ans", 1, 1, 40, 4.0),
        )
    ]
    gates = evaluate_gates(pairs)
    assert gates["p1_c0"] == 1
    assert gates["p1_c1"] == 1
    assert gates["proposal"] == "Go"
