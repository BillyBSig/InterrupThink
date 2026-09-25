"""The citation checker returns a patch and the same drafter continues."""

import importlib.util
from pathlib import Path

from interrupthink import FakeLlm, ScriptedMonitor, run_session

REPO = Path(__file__).resolve().parents[1]
CITATION = "Varghese v. China Southern Airlines, 925 F.3d 1339 (11th Cir. 2019)"
UNCHECKED = f"The filing cites {CITATION}."
CHECKER_ANSWER = "The citation was not found."
CONTINUED = "The filing note omits the citation that was not found."
HANDRAISE = (
    '<step kind="tool_intent" reversible="true">'
    '{"name":"lookup_citation","args":{"query":"' + CITATION + '"}}</step>\n'
    '<step kind="claim">ask the checker</step>\n'
    "<answer>" + UNCHECKED + "</answer>\n"
)
CONTINUATION = (
    '<step kind="tool_intent" reversible="true">'
    '{"name":"lookup_citation","args":{"query":"' + CITATION + '"}}</step>\n'
    '<step kind="claim">the filing note can be finished</step>\n'
    "<answer>" + CONTINUED + "</answer>\n"
)


def _example():
    path = REPO / "examples" / "citation_consult.py"
    spec = importlib.util.spec_from_file_location("citation_consult", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _checker_document(composed: str) -> str:
    visible = composed.replace("<", "[").replace(">", "]")
    tool = (
        '<step kind="tool_intent" reversible="true">'
        '{"name":"lookup_citation","args":{"query":"again"}}</step>'
    )
    return f'<step kind="claim">{visible}</step>\n{tool}\n<answer>{CHECKER_ANSWER}</answer>'


def _scripted_checker(composed: str):
    checker = FakeLlm([_checker_document(composed)])
    checker.apply_resume(composed)
    return checker


def test_unnamed_checker_can_commit_the_unchecked_citation():
    original = FakeLlm([HANDRAISE])
    first = run_session(llm=original, monitor=ScriptedMonitor(trigger_kind=None))
    assert first.consult_to == ""
    assert first.committed_answer == UNCHECKED
    assert original.request_index == 1


def test_checker_patch_keeps_the_citation_out_of_the_committed_note():
    example = _example()
    monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="ask the checker",
        consult_to="checker",
    )
    original = FakeLlm([HANDRAISE, CONTINUATION])
    first = run_session(llm=original, monitor=monitor)
    first, consult, resumed, received = example.handoff_consult(
        first,
        original,
        example.TASK,
        monitor,
        _scripted_checker,
    )
    note = next(event.payload for event in first.events if event.type == "floor.consult")
    assert received == example.receiver_input(example.TASK, note, "checker", "named consult")
    assert first.committed_answer is None
    assert UNCHECKED not in str(note["prefix"])
    assert consult is not None
    assert example.TASK in consult.prefix
    assert "role: checker" in consult.prefix
    assert "reason: named consult" in consult.prefix
    assert "ask the checker" in consult.prefix
    assert "do not repeat: lookup_citation" in consult.prefix
    assert UNCHECKED not in consult.prefix
    assert consult.committed_answer == CHECKER_ANSWER
    assert consult.tool_calls == []
    denied = [row["name"] for row in consult.log_records if row["event"] == "tool.policy.deny"]
    assert denied == ["lookup_citation"]
    assert resumed is not None
    assert resumed.committed_answer == CONTINUED
    assert CITATION not in resumed.committed_answer
    assert resumed.consult_to == ""
    injected = [
        event.payload["patch"]["directive"]
        for event in resumed.events
        if event.type == "floor.inject"
    ]
    assert injected == [CHECKER_ANSWER]
    assert original.request_index == 2


def test_live_checker_receives_the_package_as_its_prompt():
    example = _example()
    composed = "\n".join(
        [
            example.TASK,
            "role: checker",
            "reason: named consult",
            "kept step",
            "do not repeat: lookup_citation",
        ]
    )
    checker = example.live_checker(composed)
    assert checker.user_prompt.startswith(composed)
    assert "lookup_citation" in checker.user_prompt
    assert "citation was not found" in checker.user_prompt


def test_lookup_result_reaches_the_checker_package():
    example = _example()
    note = {
        "prefix": "<step>kept</step>",
        "tool_calls": [{"name": "lookup_citation", "args": {"query": "x"}, "result": example.NOT_FOUND}],
    }
    received = example.receiver_input(example.TASK, note, "checker", "named consult")
    assert f"result lookup_citation: {example.NOT_FOUND}" in received
    assert "do not repeat: lookup_citation" in received


def test_example_uses_the_live_model_only():
    text = (REPO / "examples" / "citation_consult.py").read_text(encoding="utf-8")
    assert "LiveLlm" in text
    assert "FakeLlm" not in text
    assert "def receiver_input" in text
    assert "from interrupthink." not in text
    assert "transfer_to_" not in text
    assert "langgraph" not in text.lower()
    assert "langchain" not in text.lower()
