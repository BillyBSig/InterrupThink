"""Public example: host denies publish after Ok and reversible=true."""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _example():
    path = REPO / "examples" / "dummy" / "tool_policy_deny.py"
    spec = importlib.util.spec_from_file_location("tool_policy_deny", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_ok_monitor_still_denies_publish_name():
    result, tool = _example().run_policy_deny()
    assert result.interrupt_ids == []
    assert result.request_count == 1
    assert tool.calls == [{"name": "save_draft", "args": {"doc": "changelog"}}]
    assert result.tool_calls == tool.calls
    denied = [r for r in result.log_records if r.get("event") == "tool.policy.deny"]
    assert [r.get("name") for r in denied] == ["publish"]
    assert not any(
        r.get("event") == "tool.execute" and r.get("name") == "publish"
        for r in result.log_records
    )
    publish_intents = [
        event
        for event in result.events
        if event.type == "tool.intent" and event.payload.get("name") == "publish"
    ]
    assert publish_intents
    assert all(event.payload.get("reversible") is True for event in publish_intents)
    assert result.committed_answer == "Changelog is ready to publish."


def test_example_needs_no_key_and_names_the_policy():
    text = (REPO / "examples" / "dummy" / "tool_policy_deny.py").read_text(encoding="utf-8")
    assert 'reversible="true"' in text
    assert '"name":"publish"' in text
    assert "tool_policy=host_allows" in text
    assert "trigger_kind=None" in text
    assert "from src." not in text
    assert "OPENAI" not in text
    assert "subprocess" not in text
