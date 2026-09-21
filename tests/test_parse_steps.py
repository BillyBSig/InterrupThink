import pytest

from src.parse.steps import ParseError, parse_steps


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


def test_tool_intent_json_and_reversible():
    doc = parse_steps(
        '<step kind="tool_intent" reversible="false">{"name":"fetch","args":{"q":1}}</step>'
    )
    unit = doc.units[0]
    assert unit.kind == "tool_intent"
    assert unit.reversible is False
    assert unit.tool == {"name": "fetch", "args": {"q": 1}}
