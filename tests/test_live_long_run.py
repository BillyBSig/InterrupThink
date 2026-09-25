"""The three-note live runner stays out of pytest. No provider call."""

from src.eval.live_compare import PROTOCOL
from src.eval.live_long_run import MODELS, long_prompt, make_long_tasks


def test_long_prompt_names_three_notes_before_the_stale_claim():
    task = make_long_tasks(1)[0]
    text = long_prompt(task)
    assert len(task.notes) == 3
    assert text.index(task.notes[0]) < text.index(task.notes[2])
    assert text.index(task.notes[2]) < text.index(f"the ticket host is {task.forbidden}")
    assert task.allowed not in text
    assert "<" not in text
    assert "XML" not in text
    assert PROTOCOL["n_tasks"] == 20
    assert PROTOCOL["primary_metric"] == "violation_rate"


def test_three_models_are_locked_and_run_separately(monkeypatch, tmp_path):
    seen = []

    def capture(**kwargs):
        seen.append((kwargs["llm"].model, kwargs["monitor"].trigger_kinds, kwargs["llm"].user_prompt))

    monkeypatch.setattr("src.eval.live_long_run.run_session", capture)
    monkeypatch.setattr("src.eval.live_long_run.load_dotenv", lambda: None)
    from src.eval.live_long_run import run_models

    summary = run_models(sandbox=tmp_path, n=1, models=MODELS)
    assert [item[0] for item in seen] == [
        "gpt-5.4-mini",
        "gpt-5.4-mini",
        "gpt-5.6-luna",
        "gpt-5.6-luna",
        "gpt-5.6-terra",
        "gpt-5.6-terra",
    ]
    assert {item[1] for item in seen} == {("claim", "tool_intent")}
    assert all("prod-0.txt" in item[2] and "stage-0.txt" not in item[2] for item in seen)
    assert summary["pooled"] is False
    assert set(summary["models"]) == set(MODELS)
    for model in MODELS:
        assert set(summary["models"][model]["by_condition"]) == {"cancel", "patch"}
        assert summary["models"][model]["cancel_minus_patch"] is not None


def test_resume_tells_the_model_the_notes_are_already_written(tmp_path):
    from src.eval.live_long_run import LongProseLlm

    task = make_long_tasks(1)[0]
    llm = LongProseLlm(
        task,
        note_paths=tuple(tmp_path / name for name in task.notes),
        user_prompt=long_prompt(task),
        api_key="not-used",
        model="not-called",
    )
    llm.apply_resume(f"<step>kept {task.notes[0]}</step>")
    correction, envelope = llm.prefix.split("\n\n", 1)
    assert "already written" in correction
    assert "do not plan them again" in correction
    assert f"Call the write tool for {task.allowed} with content payload now" in correction
    assert "do not emit a plan step first" in correction
    assert task.notes[0] in envelope
    assert llm.notes_in_envelope == 1
