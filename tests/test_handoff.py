"""Consult, Escalation, and Takeover compose a package and do not open a session."""

from pathlib import Path

from interrupthink import Consult, Escalation, Takeover

REPO = Path(__file__).resolve().parents[1]


class _Event:
    def __init__(self, event_type: str, payload: dict) -> None:
        self.type = event_type
        self.payload = payload


class _Result:
    def __init__(self, event) -> None:
        self.events = [event]


def _note(role_field: str, role: str) -> dict:
    return {
        role_field: role,
        "reason": "named",
        "prefix": "<step>kept</step>",
        "tool_calls": [{"name": "lookup", "args": {}, "result": "not found"}],
    }


def test_consult_escalation_and_takeover_share_the_package_text():
    note = _note("consult_to", "checker")
    consult = Consult.from_note("Draft the note.", note)
    escalation = Escalation.from_note(
        "Draft the note.",
        _note("escalate_to", "policy"),
    )
    takeover = Takeover.from_note(
        "Draft the note.",
        _note("takeover_to", "human"),
    )
    assert consult.text().split("role: ")[1].startswith("checker")
    assert "role: policy" in escalation.text()
    assert "role: human" in takeover.text()
    assert "result lookup: not found" in consult.text()
    assert "do not repeat: lookup" in takeover.text()
    editor = Takeover.from_note("Draft the note.", _note("takeover_to", "editor"))
    assert "role: editor" in editor.text()


def test_from_result_reads_the_floor_event():
    result = _Result(_Event("floor.consult", _note("consult_to", "checker")))
    package = Consult.from_result("Draft the note.", result)
    assert package.role == "checker"
    assert package.reason == "named"


def test_package_objects_do_not_open_a_session():
    text = (REPO / "src" / "runtime" / "handoff.py").read_text(encoding="utf-8")
    assert "run_session" not in text
    assert "class Consult" in text
    assert "class Escalation" in text
    assert "class Takeover" in text
