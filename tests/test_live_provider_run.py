"""The live runner stays out of pytest. No provider call."""

from interrupthink.eval import live_compare
from interrupthink.eval.live_compare import make_tasks
from interrupthink.eval.live_provider_run import STALE_PROMPT, EmphasizedLiveLlm


def test_prompt_is_locked_and_names_only_the_stale_file():
    text = STALE_PROMPT.format(forbidden="prod-0.txt")
    assert "prod-0.txt" in text
    assert "stage-0.txt" not in text
    assert "FakeLlm" not in STALE_PROMPT
    assert live_compare.PROTOCOL["n_tasks"] == 20
    assert live_compare.PROTOCOL["primary_metric"] == "violation_rate"


def test_resume_correction_leads_the_prefix_without_a_provider_call():
    task = make_tasks(1)[0]
    llm = EmphasizedLiveLlm(
        task,
        user_prompt=STALE_PROMPT.format(forbidden=task.forbidden),
        api_key="not-used",
        model="not-called",
    )
    llm.apply_resume("<step>kept draft</step>")
    correction, envelope = llm.prefix.split("\n\n", 1)
    assert "<" not in correction
    assert envelope == "<step>kept draft</step>"
    assert f"The first pass treated {task.forbidden}" in correction
    assert f"The correct instruction is to write {task.allowed}." in correction
    assert "STOP." not in llm.prefix
    assert llm.user_prompt.startswith("A stale ticket")
    llm.apply_resume(None)
    assert llm.prefix is None
