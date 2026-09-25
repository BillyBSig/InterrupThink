import pytest

from interrupthink.parse.steps import ParseError, parse_steps


def test_happy_xml_sequential_ids_and_answer():
    doc = parse_steps(
        """
        <step kind="plan">first</step>
        <step kind="premise">second</step>
        <answer>done</answer>
        """
    )
    assert [u.id for u in doc.units] == ["tu_01", "tu_02"]
    assert doc.units[0].parent_id == "tu_00"
    assert doc.units[1].parent_id == "tu_01"
    assert doc.units[0].kind == "plan"
    assert doc.answer == "done"


def test_missing_step_raises():
    with pytest.raises(ParseError, match="no <step>"):
        parse_steps("<answer>only</answer>")


def test_unknown_kind_raises():
    with pytest.raises(ParseError, match="unknown step kind"):
        parse_steps('<step kind="secret">nope</step>')


def test_start_n_continues_ids():
    doc = parse_steps('<step kind="claim">later</step>', start_n=3)
    assert doc.units[0].id == "tu_03"


def test_plain_lines_and_reversible_tool():
    doc = parse_steps(
        "\n".join(
            [
                "plan: first",
                "claim: the host is staging",
                'tool_intent reversible: {"name":"write","args":{"path":"staging.txt"}}',
                "answer: Wrote staging.",
            ]
        )
    )
    assert [unit.kind for unit in doc.units] == ["plan", "claim", "tool_intent"]
    assert doc.units[2].reversible is True
    assert doc.units[2].tool["args"]["path"] == "staging.txt"
    assert doc.answer == "Wrote staging."


def test_hallucinated_tool_intent_line_falls_back_to_claim():
    """A narrative line that merely starts with the reserved word must not
    crash the session. Only a well-formed JSON body is a real tool call
    (real calls are built by src.providers.live.tool_call_step)."""
    doc = parse_steps("plan: outline\ntool_intent:\nanswer: done")
    assert [u.kind for u in doc.units] == ["plan", "claim"]
    assert doc.units[1].text == "tool_intent:"
    assert doc.answer == "done"


def test_tool_intent_with_bad_json_falls_back_to_claim():
    doc = parse_steps('tool_intent: not json at all')
    assert doc.units[0].kind == "claim"
    assert doc.units[0].text == "tool_intent: not json at all"


def test_tool_intent_json_and_reversible():
    doc = parse_steps(
        '<step kind="tool_intent" reversible="false">{"name":"fetch","args":{"q":1}}</step>'
    )
    unit = doc.units[0]
    assert unit.kind == "tool_intent"
    assert unit.reversible is False
    assert unit.tool == {"name": "fetch", "args": {"q": 1}}
