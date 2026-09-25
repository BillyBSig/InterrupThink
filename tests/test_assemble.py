import pytest

from interrupthink import SessionError
from interrupthink.parse.assemble import StepAssembler, answer_text, is_answer_fragment


def test_assembler_yields_complete_steps_only():
    asm = StepAssembler()
    assert asm.feed("<step kind=\"plan\">") == []
    got = asm.feed("keep</step><step kind=\"premise\">Q3</step>")
    assert len(got) == 2
    assert "plan" in got[0]
    assert "Q3" in got[1]


def test_assembler_answer_and_fences():
    asm = StepAssembler()
    chunks = asm.feed("```xml\n<step kind=\"plan\">p</step>\n<answer>Paris</answer>\n```")
    assert len(chunks) == 2
    assert is_answer_fragment(chunks[1])
    assert answer_text(chunks[1]) == "Paris"


def test_incomplete_stream_over_cap_is_session_error():
    asm = StepAssembler(max_bytes=32)
    with pytest.raises(SessionError, match="buffer cap"):
        for _ in range(20):
            asm.feed("<step")


def test_short_complete_xml_stays_under_cap():
    asm = StepAssembler(max_bytes=32)
    got = asm.feed('<step kind="plan">ok</step>')
    assert got == ['<step kind="plan">ok</step>']
    assert asm.buf == ""
