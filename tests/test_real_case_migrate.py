"""Staging host mistaken for production; migrate must not run."""

from interrupthink import DummyTool, FakeLlm, JsonlLogger, Patch, ScriptedMonitor, run_session

MIGRATE_WRONG = """
<step kind="plan">apply the schema migration from the ticket</step>
<step kind="premise">db.example.com is production</step>
<step kind="tool_intent" reversible="false">{"name":"migrate","args":{"host":"db.example.com"}}</step>
<answer>Migrated production at db.example.com.</answer>
"""

MIGRATE_CORRECTED = """
<step kind="claim">db.example.com is staging this week; production is prod-db.internal</step>
<answer>Do not migrate. The ticket host is staging, not production.</answer>
"""


def _supervisor() -> ScriptedMonitor:
    return ScriptedMonitor(
        trigger_kind="premise",
        trigger_contains="production",
        patch=Patch(
            from_agent="A",
            target_unit_id="",
            rollback_to=None,
            diagnosis="db.example.com is staging this week, not production",
            missing="production host is prod-db.internal; do not migrate staging",
            directive="resume without migrate; treat ticket host as staging",
            preserve=[],
        ),
    )


def test_interrupt_blocks_migrate(tmp_path):
    tool = DummyTool()
    result = run_session(
        llm=FakeLlm([MIGRATE_WRONG, MIGRATE_CORRECTED]),
        monitor=_supervisor(),
        tool=tool,
        logger=JsonlLogger(tmp_path / "block.jsonl"),
    )
    assert tool.calls == []
    assert result.request_count == 2
    assert result.interrupt_ids
    assert "tool_intent" not in result.prefix
    assert "db.example.com is production" not in result.prefix
    assert "Migrated production" not in (result.committed_answer or "")
    assert "staging" in (result.committed_answer or "").lower()
    resume = next(r for r in result.log_records if r["event"] == "floor.resume")
    assert resume["mode"] == "rollback"


def test_without_interrupt_migrate_runs(tmp_path):
    tool = DummyTool()
    result = run_session(
        llm=FakeLlm([MIGRATE_WRONG]),
        monitor=ScriptedMonitor(trigger_kind=None),
        tool=tool,
        logger=JsonlLogger(tmp_path / "run.jsonl"),
        execute_tools_when_ok=True,
    )
    assert result.interrupt_ids == []
    assert tool.calls == [{"name": "migrate", "args": {"host": "db.example.com"}}]
    assert "Migrated production" in (result.committed_answer or "")
