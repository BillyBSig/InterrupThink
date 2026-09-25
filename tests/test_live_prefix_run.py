"""The draft-then-claim runner stays out of pytest. No provider call."""

from pathlib import Path

from interrupthink.eval.live_compare import PROTOCOL, _prefix_first
from interrupthink.eval.live_prefix_run import (
    ProsePrefixLlm,
    clean_prompt,
    make_prefix_tasks,
    prose_clean_prompt,
    prose_wedge_prompt,
    wedge_prompt,
)
from interrupthink.eval.live_provider_run import STALE_PROMPT, prose_correction


def test_wedge_prompt_writes_the_draft_before_the_stale_claim():
    task = make_prefix_tasks(1)[0]
    text = wedge_prompt(task)
    assert text.index(task.draft) < text.index(f"the ticket host is {task.forbidden}")
    assert task.allowed not in text
    assert _prefix_first(task) in text
    assert "stage-0.txt" not in STALE_PROMPT
    assert PROTOCOL["n_tasks"] == 20
    assert PROTOCOL["primary_metric"] == "violation_rate"


def test_prose_opening_has_no_step_tags():
    task = make_prefix_tasks(1)[0]
    wedge = prose_wedge_prompt(task)
    clean = prose_clean_prompt(task)
    assert "<" not in wedge
    assert "<" not in clean
    assert "XML" not in wedge
    assert wedge.index(task.draft) < wedge.index(f"the ticket host is {task.forbidden}")
    assert task.allowed not in wedge
    assert task.forbidden not in clean
    assert clean.index(task.draft) < clean.index(f"the ticket host is {task.allowed}")


def test_clean_prompt_does_not_name_the_forbidden_file():
    task = make_prefix_tasks(1)[0]
    text = clean_prompt(task)
    assert task.forbidden not in text
    assert task.allowed in text
    assert text.index(task.draft) < text.index(f"the ticket host is {task.allowed}")


def test_native_tools_are_opt_in():
    task = make_prefix_tasks(1)[0]
    plain = ProsePrefixLlm(
        task,
        draft_path=Path("/tmp/does-not-exist-draft.txt"),
        user_prompt="q",
        api_key="not-used",
        model="not-called",
    )
    armed = ProsePrefixLlm(
        task,
        draft_path=Path("/tmp/does-not-exist-draft.txt"),
        user_prompt="q",
        api_key="not-used",
        model="not-called",
        native_tools=True,
    )
    assert plain.tools == []
    assert armed.tools[0]["name"] == "write"
    assert armed.tools[0]["type"] == "function"


def test_explicit_model_is_forwarded_without_a_provider_call(monkeypatch, tmp_path):
    seen = []

    def capture(**kwargs):
        seen.append(kwargs["llm"].model)

    monkeypatch.setattr("interrupthink.eval.live_prefix_run.run_session", capture)
    monkeypatch.setattr("interrupthink.eval.live_prefix_run.load_dotenv", lambda: None)
    from interrupthink.eval.live_prefix_run import run_family

    summary = run_family(
        sandbox=tmp_path,
        n=1,
        prose=True,
        native_tools=True,
        model="gpt-5.6-terra",
    )
    assert seen == ["gpt-5.6-terra", "gpt-5.6-terra", "gpt-5.6-terra"]
    assert summary["model"] == "gpt-5.6-terra"
    assert summary["provider_called"] is True


def test_early_guard_fires_on_a_tool_intent_that_names_the_forbidden_path():
    from interrupthink.eval.live_prefix_run import _early_prefix_monitor
    from interrupthink.parse.steps import parse_steps

    task = make_prefix_tasks(1)[0]
    monitor = _early_prefix_monitor(task)
    doc = parse_steps(
        f'<step kind="tool_intent" reversible="false">'
        f'{{"name":"write","args":{{"path":"{task.forbidden}","content":"payload"}}}}'
        f"</step>"
    )
    verdict = monitor.verdict(doc.units[0])
    assert verdict.status == "False"
    assert verdict.patch is not None


def test_early_guard_does_not_fire_on_the_draft_write():
    from interrupthink.eval.live_prefix_run import _early_prefix_monitor
    from interrupthink.parse.steps import parse_steps

    task = make_prefix_tasks(1)[0]
    monitor = _early_prefix_monitor(task)
    doc = parse_steps(
        f'<step kind="tool_intent" reversible="true">'
        f'{{"name":"write","args":{{"path":"{task.draft}","content":"reviewed draft"}}}}'
        f"</step>"
    )
    assert monitor.verdict(doc.units[0]).status == "Ok"


def test_early_guard_is_opt_in_on_the_family_runner(monkeypatch, tmp_path):
    seen = []

    def capture(**kwargs):
        seen.append(kwargs["monitor"].trigger_kinds)

    monkeypatch.setattr("interrupthink.eval.live_prefix_run.run_session", capture)
    monkeypatch.setattr("interrupthink.eval.live_prefix_run.load_dotenv", lambda: None)
    from interrupthink.eval.live_prefix_run import run_family

    run_family(
        sandbox=tmp_path / "old",
        n=1,
        prose=True,
        native_tools=True,
        model="gpt-5.6-luna",
        include_clean=False,
    )
    run_family(
        sandbox=tmp_path / "new",
        n=1,
        prose=True,
        native_tools=True,
        model="gpt-5.6-luna",
        include_clean=False,
        early_guard=True,
    )
    assert seen[:2] == [None, None]
    assert seen[2:] == [("claim", "tool_intent"), ("claim", "tool_intent")]


def test_only_clean_skips_the_contrast_and_hides_the_forbidden_name(monkeypatch, tmp_path):
    seen = []

    def capture(**kwargs):
        seen.append((kwargs["llm"].user_prompt, kwargs["monitor"].trigger_kinds))

    monkeypatch.setattr("interrupthink.eval.live_prefix_run.run_session", capture)
    monkeypatch.setattr("interrupthink.eval.live_prefix_run.load_dotenv", lambda: None)
    from interrupthink.eval.live_prefix_run import run_family

    summary = run_family(
        sandbox=tmp_path,
        n=1,
        prose=True,
        native_tools=True,
        model="gpt-5.6-luna",
        early_guard=True,
        only_clean=True,
    )
    assert len(seen) == 1
    prompt, kinds = seen[0]
    assert "prod-0.txt" not in prompt
    assert "stage-0.txt" in prompt
    assert "<" not in prompt
    assert kinds == ("claim", "tool_intent")
    assert set(summary["by_condition"]) == {"clean"}
    assert summary["cancel_minus_patch"] is None


def test_resume_uses_the_locked_prose_and_records_the_draft():
    task = make_prefix_tasks(1)[0]
    llm = ProsePrefixLlm(
        task,
        draft_path=Path("/tmp/does-not-exist-draft.txt"),
        user_prompt=wedge_prompt(task),
        api_key="not-used",
        model="not-called",
    )
    llm.apply_resume(f"<step>kept {task.draft}</step>")
    correction, envelope = llm.prefix.split("\n\n", 1)
    assert correction == prose_correction(task.forbidden, task.allowed)
    assert "<" not in correction
    assert task.draft in envelope
    assert llm.draft_in_envelope == 1
    assert llm.draft_at_resume == 0
    llm.apply_resume(None)
    assert llm.prefix is None


def test_comparators_keep_the_prose_protocol_and_do_not_call_the_provider(monkeypatch, tmp_path):
    seen = []

    def capture(**kwargs):
        monitor = kwargs["monitor"]
        seen.append((kwargs["llm"].model, kwargs["llm"].user_prompt, monitor.trigger_kind, monitor.trigger_contains, kwargs["tool_policy"]))

    monkeypatch.setattr("interrupthink.eval.live_prefix_run.run_session", capture)
    monkeypatch.setattr("interrupthink.eval.live_prefix_run.load_dotenv", lambda: None)
    from interrupthink.eval.live_prefix_run import run_comparators

    summary = run_comparators(sandbox=tmp_path, n=1, model="gpt-5.6-luna")
    assert [item[0] for item in seen] == ["gpt-5.6-luna", "gpt-5.6-luna", "gpt-5.6-luna"]
    assert all("<" not in item[1] and "prod-0.txt" in item[1] for item in seen)
    assert seen[0][2] is None and seen[0][4] is None
    assert seen[1][2] is None and seen[1][4]("write", {"path": "prod-0.txt"}) is False
    assert seen[1][4]("write", {"path": "draft-0.txt"}) is True
    assert seen[1][4]("write", {"path": "stage-0.txt"}) is True
    assert seen[2][2] == "answer_draft" and seen[2][3] == "prod-0.txt" and seen[2][4] is None
    assert summary["primary_metric"] == "violation_rate"
    assert summary["model"] == "gpt-5.6-luna"
    assert set(summary["by_condition"]) == {"none", "host_policy", "final_answer"}


def test_contrast_can_omit_the_clean_twin(monkeypatch, tmp_path):
    seen = []

    def capture(**kwargs):
        seen.append(kwargs["llm"].user_prompt)

    monkeypatch.setattr("interrupthink.eval.live_prefix_run.run_session", capture)
    monkeypatch.setattr("interrupthink.eval.live_prefix_run.load_dotenv", lambda: None)
    from interrupthink.eval.live_prefix_run import run_family

    summary = run_family(
        sandbox=tmp_path,
        n=1,
        prose=True,
        native_tools=True,
        model="gpt-5.4-mini",
        include_clean=False,
    )
    assert len(seen) == 2
    assert all("prod-0.txt" in prompt and "<" not in prompt for prompt in seen)
    assert summary["model"] == "gpt-5.4-mini"
    assert set(summary["by_condition"]) == {"cancel", "patch"}
    assert "cancel_minus_patch" in summary
