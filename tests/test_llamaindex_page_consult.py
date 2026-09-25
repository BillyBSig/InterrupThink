"""The checker receives the retrieved page and the same assistant stays within it."""

import importlib.util
from pathlib import Path

from interrupthink import FakeLlm, ScriptedMonitor

REPO = Path(__file__).resolve().parents[1]
BAD = "Yes, exchanges are available any time."
CHECKER_ANSWER = "Exchanges after 30 days are not offered."
CONTINUED = "Exchanges after 30 days are not offered."
HANDRAISE = (
    '<step kind="tool_intent" reversible="true">'
    '{"name":"retrieve_page","args":{"query":"exchange after 30 days"}}</step>\n'
    '<step kind="claim">ask the checker</step>\n'
    "<answer>" + BAD + "</answer>\n"
)
CONTINUATION = (
    '<step kind="claim">the reply can be finished</step>\n'
    "<answer>" + CONTINUED + "</answer>\n"
)


def _example():
    path = REPO / "examples" / "llamaindex_page_consult.py"
    spec = importlib.util.spec_from_file_location("llamaindex_page_consult", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _checker_document(composed: str) -> str:
    visible = composed.replace("<", "[").replace(">", "]")
    tool = (
        '<step kind="tool_intent" reversible="true">'
        '{"name":"retrieve_page","args":{"query":"again"}}</step>'
    )
    return f'<step kind="claim">{visible}</step>\n{tool}\n<answer>{CHECKER_ANSWER}</answer>'


def _scripted_checker(composed: str):
    checker = FakeLlm([_checker_document(composed)])
    checker.apply_resume(composed)
    return checker


def test_unnamed_assistant_can_answer_beyond_the_page():
    example = _example()
    assistant = FakeLlm([HANDRAISE])
    result = example.run_page_consult(
        ScriptedMonitor(trigger_kind=None),
        assistant,
        _scripted_checker,
    )
    assert result.first.consult_to == ""
    assert result.first.committed_answer == BAD
    assert result.resumed is None
    assert assistant.request_index == 1


def test_checker_receives_the_page_and_the_same_assistant_stays_inside_it():
    example = _example()
    monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="ask the checker",
        consult_to="checker",
    )
    assistant = FakeLlm([HANDRAISE, CONTINUATION])
    result = example.run_page_consult(monitor, assistant, _scripted_checker)
    note = next(event.payload for event in result.first.events if event.type == "floor.consult")
    assert result.package == example.receiver_input(example.TASK, note, "checker", "named consult")
    assert f"result retrieve_page: {example.PAGE}" in result.package
    assert "do not repeat: retrieve_page" in result.package
    assert result.first.committed_answer is None
    assert BAD not in str(note["prefix"])
    assert result.consult.committed_answer == CHECKER_ANSWER
    assert result.resumed.committed_answer == CONTINUED
    assert "any time" not in result.resumed.committed_answer
    assert example.PAGE.split(". ")[1] in result.resumed.committed_answer
    injected = [
        event.payload["patch"]["directive"]
        for event in result.resumed.events
        if event.type == "floor.inject"
    ]
    assert injected == [CHECKER_ANSWER]
    denied = [row["name"] for row in result.consult.log_records if row["event"] == "tool.policy.deny"]
    assert denied == ["retrieve_page"]
    assert assistant.request_index == 2


def test_host_retrieves_the_page_when_the_assistant_skipped_it():
    example = _example()

    class _Event:
        type = "floor.consult"
        payload = {
            "consult_to": "checker",
            "reason": "named consult",
            "prefix": "<step>ask the checker</step>",
            "tool_calls": [],
            "unit_id": "u1",
        }

    class _First:
        consult_to = "checker"
        events = [_Event()]

    tool = example.PageRetrieve(example.build_retriever())
    composed, written = example.compose_consult(_First(), example.TASK, tool)
    assert example.PAGE in composed
    assert written == {"retrieve_page"}


def test_example_index_does_not_continue_the_chat():
    text = (REPO / "examples" / "llamaindex_page_consult.py").read_text(encoding="utf-8")
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    lock = (REPO / "uv.lock").read_text(encoding="utf-8")
    assert "LiveLlm" in text
    assert "FakeLlm" not in text
    assert "Consult" in text
    assert "def receiver_input" in text
    assert "VectorStoreIndex" in text
    assert "as_retriever" in text
    assert "as_chat_engine" not in text
    assert "QueryEngine" not in text
    assert "from interrupthink." not in text
    assert "transfer_to_" not in text
    assert "llama-index" not in pyproject
    assert "llama_index" not in pyproject
    assert 'name = "llama-index"' not in lock
