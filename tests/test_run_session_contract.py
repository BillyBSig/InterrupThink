"""User-facing run_session contract. Dummy. No API key."""

import json

import pytest

from interrupthink import DummyTool, FakeLlm, JsonlLogger, ScriptedMonitor, SessionError, run_session
from interrupthink.eval.g1 import INTERRUPT_XML_1, INTERRUPT_XML_2, run_path
from interrupthink.runtime.events import Patch, Verdict

KEEP_PROMPT = "publish the changelog if approved"
WRONG = """
<step kind="plan">publish the changelog now</step>
<step kind="premise">the changelog is already approved</step>
<step kind="tool_intent" reversible="false">{"name":"publish","args":{"doc":"changelog"}}</step>
<answer>Published the changelog.</answer>
"""
STOPPED = """
<step kind="claim">changelog is not approved; do not publish</step>
<answer>Did not publish.</answer>
"""


def test_missing_resume_document_is_session_error():
    llm = FakeLlm([WRONG])
    monitor = ScriptedMonitor(trigger_kind="premise", trigger_contains="already approved")
    with pytest.raises(SessionError, match="second document"):
        run_session(llm=llm, monitor=monitor, tool=DummyTool())


def test_run_session_does_not_rewrite_osaka_prompt():
    llm = FakeLlm([WRONG, STOPPED])
    llm.trial_seed = "s0"
    llm.user_prompt = KEEP_PROMPT
    monitor = ScriptedMonitor(trigger_kind="premise", trigger_contains="already approved")
    result = run_session(llm=llm, monitor=monitor, tool=DummyTool())
    assert result.interrupt_ids
    assert llm.user_prompt == KEEP_PROMPT
    assert "Osaka" not in llm.user_prompt
    assert "Kansai" not in llm.user_prompt


def test_user_reads_result_fields_without_log_records():
    tool = DummyTool()
    llm = FakeLlm([WRONG, STOPPED])
    monitor = ScriptedMonitor(trigger_kind="premise", trigger_contains="already approved")
    result = run_session(llm=llm, monitor=monitor, tool=tool)
    assert result.committed_answer == "Did not publish."
    assert result.interrupt_ids
    assert result.dropped_ids
    assert result.request_count == 2
    assert result.tool_calls == []
    assert tool.calls == []


class _UnknownOnAnswer:
    """Ok on steps; Unknown on the final answer (no authorization)."""

    def __init__(self) -> None:
        self.held_tool_ids: list[str] = []

    def verdict(self, unit):
        if unit.kind == "answer_draft":
            return Verdict(unit_id=unit.id, status="Unknown", reason="no authorization")
        return Verdict(unit_id=unit.id, status="Ok", reason="step pass")

    def release_tool(self, unit_id: str):
        return Verdict(unit_id=unit_id, status="Ok", reason="release")


DANGEROUS_ANSWER = """
<step kind="plan">publish the changelog now</step>
<answer>Published the changelog.</answer>
"""

HARMLESS_ANSWER = """
<step kind="plan">summarize the freeze</step>
<answer>Did not publish.</answer>
"""


def test_answer_without_ok_does_not_commit_protected_sink():
    result = run_session(
        llm=FakeLlm([DANGEROUS_ANSWER]),
        monitor=_UnknownOnAnswer(),
        tool=DummyTool(),
    )
    assert result.committed_answer is None
    assert result.watermarks.get("committed_answer") is None
    assert not any(r["event"] == "answer.commit" for r in result.log_records)
    assert any(
        r["event"] == "monitor.verdict" and r.get("status") == "Unknown"
        for r in result.log_records
    )


def test_answer_with_ok_commits_protected_sink():
    result = run_session(
        llm=FakeLlm([HARMLESS_ANSWER]),
        monitor=ScriptedMonitor(trigger_kind=None),
        tool=DummyTool(),
    )
    assert result.committed_answer == "Did not publish."
    assert any(r["event"] == "answer.commit" for r in result.log_records)


REJECTED_ANSWER = """
<step kind="plan">publish the changelog now</step>
<answer>Published the changelog.</answer>
"""
REPLACEMENT_ANSWER = """
<step kind="claim">changelog is not approved; do not publish</step>
<answer>Did not publish.</answer>
"""
ANSWER_PATCH_FACT = "do not publish; changelog is not approved"


class _PatchOnAnswer:
    """Ok on steps; one Patch on the first answer_draft, then Ok."""

    def __init__(self) -> None:
        self.held_tool_ids: list[str] = []
        self.fired = False

    def verdict(self, unit):
        if unit.kind == "answer_draft" and not self.fired:
            self.fired = True
            return Verdict(
                unit_id=unit.id,
                status="Patch",
                reason="nudge answer",
                patch=Patch(
                    from_agent="A",
                    target_unit_id=unit.id,
                    rollback_to=unit.parent_id or None,
                    diagnosis="unsafe publish",
                    missing=ANSWER_PATCH_FACT,
                    directive="refuse",
                ),
            )
        return Verdict(unit_id=unit.id, status="Ok", reason="pass")

    def release_tool(self, unit_id: str):
        return Verdict(unit_id=unit_id, status="Ok", reason="release")


def test_false_on_answer_aborts_and_resumes():
    result = run_session(
        llm=FakeLlm([REJECTED_ANSWER, REPLACEMENT_ANSWER]),
        monitor=ScriptedMonitor(
            trigger_kind="answer_draft",
            trigger_contains="Published the changelog",
        ),
        tool=DummyTool(),
    )
    assert result.committed_answer == "Did not publish."
    assert result.request_count == 2
    assert result.interrupt_ids
    assert any(r["event"] == "floor.interrupt" for r in result.log_records)


class _FalseOnAnswerNoAnchor:
    """False on answer_draft with no rollback_to."""

    def __init__(self) -> None:
        self.held_tool_ids: list[str] = []

    def verdict(self, unit):
        if unit.kind == "answer_draft":
            return Verdict(unit_id=unit.id, status="False", reason="unsupported")
        return Verdict(unit_id=unit.id, status="Ok", reason="step pass")

    def release_tool(self, unit_id: str):
        return Verdict(unit_id=unit_id, status="Ok", reason="release")


ANSWER_ONLY_FALSE = "<answer>Published the changelog.</answer>"

ANSWER_ONLY_PLAIN = "answer: Published the changelog."


class _UnknownOnAnswer:
    """Unknown on every step, including the answer. Never fires, never approves."""

    def __init__(self) -> None:
        self.held_tool_ids: list[str] = []

    def verdict(self, unit):
        return Verdict(unit_id=unit.id, status="Unknown", reason="no rule for this")

    def release_tool(self, unit_id: str):
        return Verdict(unit_id=unit_id, status="Ok", reason="release")


def test_answer_only_turn_with_unknown_verdict_does_not_crash():
    """A turn that is just one answer line, held Unknown, must not raise
    "llm produced no complete step" — the specialist did produce content,
    the monitor just never said Ok (found 2026-09-25, live multi-agent
    examples with no preceding plan/claim line)."""
    result = run_session(
        llm=FakeLlm([ANSWER_ONLY_PLAIN]),
        monitor=_UnknownOnAnswer(),
        tool=DummyTool(),
    )
    assert result.committed_answer is None
    assert not result.interrupt_ids
    assert not any(r["event"] == "answer.commit" for r in result.log_records)


def test_false_on_answer_without_anchor_holds():
    result = run_session(
        llm=FakeLlm([ANSWER_ONLY_FALSE]),
        monitor=_FalseOnAnswerNoAnchor(),
        tool=DummyTool(),
    )
    assert result.committed_answer is None
    assert result.request_count == 1
    assert not result.interrupt_ids
    assert not any(r["event"] == "floor.interrupt" for r in result.log_records)
    assert not any(r["event"] == "answer.commit" for r in result.log_records)
    assert any(r["event"] == "answer.rejected" for r in result.log_records)
    assert any(
        r["event"] == "monitor.verdict" and r.get("status") == "False"
        for r in result.log_records
    )


def test_patch_on_answer_aborts_and_prefix_carries_fact():
    llm = FakeLlm([REJECTED_ANSWER, REPLACEMENT_ANSWER])
    result = run_session(
        llm=llm,
        monitor=_PatchOnAnswer(),
        tool=DummyTool(),
    )
    assert result.committed_answer == "Did not publish."
    assert result.request_count == 2
    assert result.interrupt_ids
    assert ANSWER_PATCH_FACT in (llm.resume_envelope or "")
    assert ANSWER_PATCH_FACT in result.prefix


SECRET_MARK = "USER_EMAIL_secret_fixture@example.invalid"
SECRET_XML = f"""
<step kind="plan">summarize for {SECRET_MARK}</step>
<answer>Did not publish.</answer>
"""


def test_default_logger_redacts_unit_text(tmp_path):
    log_path = tmp_path / "session.jsonl"
    result = run_session(
        llm=FakeLlm([SECRET_XML]),
        monitor=ScriptedMonitor(trigger_kind=None),
        tool=DummyTool(),
        logger=JsonlLogger(log_path),
    )
    blob = json.dumps(result.log_records)
    on_disk = log_path.read_text(encoding="utf-8")
    assert SECRET_MARK not in blob
    assert SECRET_MARK not in on_disk
    thought = next(r for r in result.log_records if r["event"] == "thought.unit")
    assert thought["text"]["redacted"] is True
    assert result.committed_answer == "Did not publish."


def test_opt_in_logger_keeps_unit_text():
    logger = JsonlLogger(redact=False)
    result = run_session(
        llm=FakeLlm([SECRET_XML]),
        monitor=ScriptedMonitor(trigger_kind=None),
        tool=DummyTool(),
        logger=logger,
    )
    blob = json.dumps(result.log_records)
    assert SECRET_MARK in blob
    thought = next(r for r in result.log_records if r["event"] == "thought.unit")
    assert SECRET_MARK in thought["text"]


SECRET_ANSWER_XML = f"""
<step kind="plan">summarize the freeze</step>
<answer>Did not publish. Contact {SECRET_MARK}</answer>
"""


class _ReasonWithSecret:
    """Ok every unit; reason carries the secret fixture."""

    def __init__(self) -> None:
        self.held_tool_ids: list[str] = []

    def verdict(self, unit):
        return Verdict(unit_id=unit.id, status="Ok", reason=f"pass {SECRET_MARK}")

    def release_tool(self, unit_id: str):
        return Verdict(unit_id=unit_id, status="Ok", reason="release")


def test_default_logger_redacts_secret_in_answer(tmp_path):
    log_path = tmp_path / "answer.jsonl"
    result = run_session(
        llm=FakeLlm([SECRET_ANSWER_XML]),
        monitor=ScriptedMonitor(trigger_kind=None),
        tool=DummyTool(),
        logger=JsonlLogger(log_path),
    )
    blob = json.dumps(result.log_records)
    on_disk = log_path.read_text(encoding="utf-8")
    assert SECRET_MARK not in blob
    assert SECRET_MARK not in on_disk
    commit = next(r for r in result.log_records if r["event"] == "answer.commit")
    assert commit["text"]["redacted"] is True
    assert SECRET_MARK in result.committed_answer


def test_default_logger_redacts_monitor_reason(tmp_path):
    log_path = tmp_path / "reason.jsonl"
    result = run_session(
        llm=FakeLlm([HARMLESS_ANSWER]),
        monitor=_ReasonWithSecret(),
        tool=DummyTool(),
        logger=JsonlLogger(log_path),
    )
    blob = json.dumps(result.log_records)
    on_disk = log_path.read_text(encoding="utf-8")
    assert SECRET_MARK not in blob
    assert SECRET_MARK not in on_disk
    verdict = next(r for r in result.log_records if r["event"] == "monitor.verdict")
    assert verdict["reason"]["redacted"] is True


def test_opt_in_logger_keeps_answer_and_reason():
    logger = JsonlLogger(redact=False)
    result = run_session(
        llm=FakeLlm([SECRET_ANSWER_XML]),
        monitor=_ReasonWithSecret(),
        tool=DummyTool(),
        logger=logger,
    )
    blob = json.dumps(result.log_records)
    assert SECRET_MARK in blob
    commit = next(r for r in result.log_records if r["event"] == "answer.commit")
    assert SECRET_MARK in commit["text"]
    verdict = next(r for r in result.log_records if r["event"] == "monitor.verdict")
    assert SECRET_MARK in verdict["reason"]


class _FalseEveryPremise:
    """Interrupt every request so the session can hit the request cap."""

    def __init__(self) -> None:
        self.held_tool_ids: list[str] = []

    def verdict(self, unit):
        if unit.kind != "premise":
            return Verdict(unit_id=unit.id, status="Ok", reason="pass")
        parent = unit.parent_id
        patch = Patch(
            from_agent="A",
            target_unit_id=unit.id,
            rollback_to=parent,
            diagnosis="repeat interrupt",
            missing="corrected premise",
            directive="do not publish",
            preserve=[parent] if parent else [],
        )
        return Verdict(
            unit_id=unit.id,
            status="False",
            reason="repeat interrupt",
            patch=patch,
            rollback_to=parent,
        )

    def release_tool(self, unit_id: str):
        return Verdict(unit_id=unit_id, status="Ok", reason="release")


REPEAT_INTERRUPT = """
<step kind="plan">publish the changelog now</step>
<step kind="premise">the changelog is already approved</step>
<answer>Published the changelog.</answer>
"""


def test_request_cap_without_commit_is_session_error():
    llm = FakeLlm([REPEAT_INTERRUPT, REPEAT_INTERRUPT])
    with pytest.raises(SessionError, match="request cap"):
        run_session(
            llm=llm,
            monitor=_FalseEveryPremise(),
            tool=DummyTool(),
            max_requests=2,
        )


class _GenerateOnly:
    """generate/abort only — resume envelope would be ignored."""

    def __init__(self, documents: list[str]) -> None:
        self.documents = list(documents)
        self.request_index = 0
        self.tokens_emitted = 0
        self.tokens_wasted = 0
        self.aborted = False

    def generate(self) -> str:
        text = self.documents[self.request_index]
        self.request_index += 1
        self.tokens_emitted += 1
        return text

    def abort(self) -> None:
        self.aborted = True


def test_llm_without_apply_resume_is_session_error():
    llm = _GenerateOnly([WRONG, STOPPED])
    monitor = ScriptedMonitor(trigger_kind="premise", trigger_contains="already approved")
    with pytest.raises(SessionError, match="apply_resume"):
        run_session(llm=llm, monitor=monitor, tool=DummyTool())


def test_fake_llm_resume_envelope_is_applied():
    llm = FakeLlm([WRONG, STOPPED])
    monitor = ScriptedMonitor(trigger_kind="premise", trigger_contains="already approved")
    result = run_session(llm=llm, monitor=monitor, tool=DummyTool())
    assert result.committed_answer == "Did not publish."
    assert result.request_count == 2
    assert "publish the changelog now" in llm.resume_envelope
    assert llm.prefix == llm.resume_envelope


def test_run_path_still_applies_osaka_when_trial_seed_set(tmp_path):
    llm = FakeLlm([INTERRUPT_XML_1, INTERRUPT_XML_2])
    llm.trial_seed = "s0"
    llm.user_prompt = "start"
    result = run_path(
        "interrupt",
        llm=llm,
        logger=JsonlLogger(tmp_path / "lab.jsonl"),
    )
    assert result.interrupt_ids
    assert "Osaka" in llm.user_prompt or "Kansai" in llm.user_prompt


ECHO_TOOL = """
<step kind="plan">echo a demo value</step>
<step kind="tool_intent" reversible="true">{"name":"echo","args":{"q":1}}</step>
<answer>Did not publish.</answer>
"""


def test_tool_policy_none_is_allow_if_ok():
    tool = DummyTool()
    result = run_session(
        llm=FakeLlm([ECHO_TOOL]),
        monitor=ScriptedMonitor(trigger_kind=None),
        tool=tool,
    )
    assert tool.calls == [{"name": "echo", "args": {"q": 1}}]
    assert any(r["event"] == "tool.execute" for r in result.log_records)


def test_tool_policy_false_denies_execute():
    tool = DummyTool()
    result = run_session(
        llm=FakeLlm([ECHO_TOOL]),
        monitor=ScriptedMonitor(trigger_kind=None),
        tool=tool,
        tool_policy=lambda name, args: False,
    )
    assert tool.calls == []
    assert not any(r["event"] == "tool.execute" for r in result.log_records)
    assert any(r["event"] == "tool.policy.deny" for r in result.log_records)
