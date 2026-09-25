import io
import json
import urllib.error
from pathlib import Path
from unittest.mock import patch

import pytest

from src.eval.g1 import run_path
from src.parse.steps import parse_steps
from src.providers.live import (
    STEP_INSTRUCTIONS,
    TOOL_INSTRUCTIONS,
    LiveLlmError,
    LiveLlm,
    _cancel_response,
    _output_text,
    _responses_request,
    _strip_fences,
    sandbox_write_tool,
    tool_call_step,
)
from src.runtime.log import JsonlLogger


class _FakeHTTP:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._payload = payload
        self.status = status

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def readline(self) -> bytes:
        return b""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def close(self) -> None:
        return None


class _SSE:
    def __init__(self, events: list[dict]) -> None:
        chunks = []
        for event in events:
            chunks.append(f"data: {json.dumps(event)}\n\n")
        chunks.append("data: [DONE]\n\n")
        self._data = "".join(chunks).encode("utf-8")
        self._offset = 0
        self.closed = False
        self.status = 200

    def readline(self) -> bytes:
        if self.closed or self._offset >= len(self._data):
            return b""
        nl = self._data.find(b"\n", self._offset)
        if nl < 0:
            rest = self._data[self._offset :]
            self._offset = len(self._data)
            return rest
        line = self._data[self._offset : nl + 1]
        self._offset = nl + 1
        return line

    def close(self) -> None:
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_strip_fences_and_output_text():
    payload = {
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "```xml\n<step kind=\"plan\">x</step>\n```"}],
            }
        ]
    }
    assert "<step kind=\"plan\">x</step>" in _strip_fences(_output_text(payload))


def test_tool_call_step_starts_on_its_own_line():
    """The plain text channel has no tag boundary. A leading newline stops
    this line fusing onto an unterminated text line already in the
    stream assembler's buffer (the fusion bug found on 2026-09-25)."""
    step = tool_call_step("write", '{"path":"x.txt","content":"y"}')
    assert step.startswith("\n")
    assert step == '\ntool_intent: {"name": "write", "args": {"path": "x.txt", "content": "y"}}\n'


def test_tool_call_step_never_discards_a_malformed_call():
    """A completed function-call event must always produce a step, or a
    request can end with zero steps and the session raises ValueError
    (the silent-discard bug found on 2026-09-25)."""
    step = tool_call_step("write", '{"path": truncated')
    assert step is not None
    assert "malformed tool call" in step
    from src.parse.steps import parse_steps

    doc = parse_steps(step)
    assert doc.units[0].kind == "claim"


def test_live_llm_generate_mocked():
    xml = '<step kind="plan">p</step>\n<answer>Paris.</answer>'
    events = [
        {"type": "response.created", "response": {"id": "resp_test"}},
        {"type": "response.output_text.delta", "delta": xml},
        {"type": "response.completed", "response": {"usage": {"output_tokens": 9}}},
    ]
    llm = LiveLlm(user_prompt="q", api_key="sk-test", base_url="https://example.test/v1")
    with patch("src.providers.live.urllib.request.urlopen", return_value=_SSE(events)):
        text = llm.generate()
    assert "<step kind=\"plan\">p</step>" in text


def test_live_llm_abort_posts_cancel():
    xml = (
        '<step kind="plan">outline</step>'
        '<step kind="premise">Q3 Japan is the annual trend</step>'
        '<step kind="claim">open the warehouse</step>'
        "<answer>Open it.</answer>"
    )
    stream_events = [
        {"type": "response.created", "response": {"id": "resp_abort"}},
        {"type": "response.output_text.delta", "delta": xml},
    ]
    resume_events = [
        {"type": "response.created", "response": {"id": "resp_resume"}},
        {
            "type": "response.output_text.delta",
            "delta": '<step kind="claim">use FY rolling</step><answer>Hold the warehouse.</answer>',
        },
        {"type": "response.completed", "response": {"usage": {"output_tokens": 6}}},
    ]
    calls: list[str] = []
    streams = {"n": 0}

    def fake_open(req, timeout=0):
        url = req.get_full_url()
        calls.append(url)
        if url.endswith("/cancel"):
            return _FakeHTTP({"status": "cancelled"})
        streams["n"] += 1
        return _SSE(stream_events if streams["n"] == 1 else resume_events)

    llm = LiveLlm(
        user_prompt="q",
        api_key="sk-test",
        base_url="https://example.test/v1",
    )
    with patch("src.providers.live.urllib.request.urlopen", side_effect=fake_open):
        result = run_path("interrupt", llm=llm, logger=JsonlLogger())
    assert result.request_count == 2
    assert result.interrupt_ids
    assert "annual trend" not in result.prefix
    assert "open the warehouse" not in result.prefix
    assert any(u.endswith("/responses/resp_abort/cancel") for u in calls)
    assert llm.cancel_ok is True


def test_cancel_response_success():
    with patch(
        "src.providers.live.urllib.request.urlopen",
        return_value=_FakeHTTP({"status": "cancelled"}),
    ):
        assert _cancel_response("https://example.test/v1", "sk-test", "resp_1") is True


def test_cancel_response_http_error():
    err = urllib.error.HTTPError(
        "https://example.test/v1/responses/resp_1/cancel",
        404,
        "gone",
        hdrs=None,
        fp=io.BytesIO(b"nope"),
    )

    def fake_open(req, timeout=0):
        raise err

    with patch("src.providers.live.urllib.request.urlopen", side_effect=fake_open):
        assert _cancel_response("https://example.test/v1", "sk-test", "resp_1") is False


def test_cancel_response_os_error():
    with patch(
        "src.providers.live.urllib.request.urlopen",
        side_effect=OSError("down"),
    ):
        assert _cancel_response("https://example.test/v1", "sk-test", "resp_1") is False


def test_cancel_response_malformed_json():
    class _Bad:
        status = 200

        def read(self) -> bytes:
            return b"{not-json"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with patch("src.providers.live.urllib.request.urlopen", return_value=_Bad()):
        assert _cancel_response("https://example.test/v1", "sk-test", "resp_1") is False


def test_cancel_response_has_single_urlopen():
    text = (
        Path(__file__).resolve().parents[1] / "src" / "providers" / "live.py"
    ).read_text(encoding="utf-8")
    start = text.index("def _cancel_response")
    end = text.index("\ndef ", start + 1)
    assert text[start:end].count("urlopen") == 1


def test_chunk_speaker_stops_tail_after_abort():
    class ChunkLlm:
        def __init__(self) -> None:
            self.tokens_emitted = 0
            self.tokens_wasted = 0
            self.aborted = False
            self.prefix = None
            self._n = 0

        def iter_deltas(self):
            self._n += 1
            if self._n == 1:
                for piece in (
                    '<step kind="plan">keep plan</step>',
                    '<step kind="premise">Q3 Japan is the annual trend</step>',
                    '<step kind="claim">tail must vanish</step>',
                ):
                    if self.aborted:
                        return
                    self.tokens_emitted += 1
                    yield piece
                return
            yield (
                '<step kind="claim">use FY rolling</step>'
                "<answer>Do not treat Q3 Japan as the annual trend.</answer>"
            )

        def abort(self) -> None:
            self.aborted = True
            self.tokens_wasted += 1

        def apply_resume(self, envelope: str | None) -> None:
            self.prefix = envelope or None

        def generate(self) -> str:
            return "".join(self.iter_deltas())

    result = run_path("interrupt", llm=ChunkLlm(), logger=JsonlLogger())
    assert result.request_count == 2
    assert "tail must vanish" not in result.prefix
    assert "keep plan" in result.prefix
    assert result.committed_answer == "Do not treat Q3 Japan as the annual trend."


def test_responses_request_is_foreground_stream():
    req = _responses_request(
        base_url="https://example.test/v1",
        api_key="sk-test",
        model="gpt-test",
        effort="none",
        instructions="instr",
        user="q",
        stream=True,
    )
    body = json.loads(req.data.decode("utf-8"))
    assert body["stream"] is True
    assert body["background"] is False


def test_native_function_call_becomes_one_write_step():
    events = [
        {"type": "response.created", "response": {"id": "resp_tool"}},
        {
            "type": "response.output_item.added",
            "item": {
                "type": "function_call",
                "id": "fc_1",
                "call_id": "call_1",
                "name": "write",
                "arguments": "",
            },
        },
        {"type": "response.function_call_arguments.delta", "item_id": "fc_1", "delta": '{"path":'},
        {
            "type": "response.function_call_arguments.delta",
            "item_id": "fc_1",
            "delta": '"draft-0.txt","content":"reviewed draft"}',
        },
        {
            "type": "response.function_call_arguments.done",
            "item_id": "fc_1",
            "arguments": '{"path":"draft-0.txt","content":"reviewed draft"}',
        },
        {
            "type": "response.output_item.done",
            "item": {
                "type": "function_call",
                "id": "fc_1",
                "name": "write",
                "arguments": '{"path":"draft-0.txt","content":"reviewed draft"}',
            },
        },
        {"type": "response.completed", "response": {"usage": {"output_tokens": 4}}},
    ]
    llm = LiveLlm(
        user_prompt="q",
        api_key="sk-test",
        base_url="https://example.test/v1",
        tools=[sandbox_write_tool()],
    )
    with patch("src.providers.live.urllib.request.urlopen", return_value=_SSE(events)):
        text = llm.generate()
    parsed = parse_steps(text)
    assert len(parsed.units) == 1
    assert parsed.units[0].kind == "tool_intent"
    assert parsed.units[0].tool["name"] == "write"
    assert parsed.units[0].tool["args"]["path"] == "draft-0.txt"


def test_tools_switch_the_specialist_instructions():
    seen = {}

    def fake_open(req, timeout=0):
        seen["body"] = json.loads(req.data.decode("utf-8"))
        return _SSE([
            {"type": "response.created", "response": {"id": "resp_instr"}},
            {"type": "response.output_text.delta", "delta": "<answer>ok</answer>"},
            {"type": "response.completed", "response": {"usage": {"output_tokens": 1}}},
        ])

    plain = LiveLlm(user_prompt="q", api_key="sk-test", base_url="https://example.test/v1")
    with patch("src.providers.live.urllib.request.urlopen", fake_open):
        plain.generate()
    assert seen["body"]["instructions"] == STEP_INSTRUCTIONS
    assert "tools" not in seen["body"]

    armed = LiveLlm(
        user_prompt="q",
        api_key="sk-test",
        base_url="https://example.test/v1",
        tools=[sandbox_write_tool()],
    )
    with patch("src.providers.live.urllib.request.urlopen", fake_open):
        armed.generate()
    assert seen["body"]["instructions"] == TOOL_INSTRUCTIONS
    assert "tool_intent" not in TOOL_INSTRUCTIONS
    assert seen["body"]["tools"][0]["name"] == "write"


def test_tool_result_starts_another_model_turn():
    streams = [
        _SSE([
            {"type": "response.created", "response": {"id": "resp_1"}},
            {
                "type": "response.output_item.added",
                "item": {
                    "type": "function_call",
                    "id": "fc_1",
                    "call_id": "call_1",
                    "name": "write",
                    "arguments": "",
                },
            },
            {
                "type": "response.function_call_arguments.done",
                "item_id": "fc_1",
                "arguments": '{"path":"draft-0.txt","content":"reviewed draft"}',
            },
        ]),
        _SSE([
            {"type": "response.created", "response": {"id": "resp_2"}},
            {"type": "response.output_text.delta", "delta": '<step kind="claim">next</step>'},
            {"type": "response.completed", "response": {"usage": {"output_tokens": 2}}},
        ]),
    ]
    bodies = []

    def fake_open(req, timeout=0):
        bodies.append(json.loads(req.data.decode("utf-8")))
        return streams.pop(0)

    llm = LiveLlm(
        user_prompt="write the draft",
        api_key="sk-test",
        base_url="https://example.test/v1",
        tools=[sandbox_write_tool()],
    )
    with patch("src.providers.live.urllib.request.urlopen", fake_open):
        chunks = []
        stream = llm.iter_deltas()
        chunks.append(next(stream))
        llm.submit_tool_result("wrote draft-0.txt")
        chunks.extend(stream)
    assert "draft-0.txt" in chunks[0]
    assert "claim" in "".join(chunks[1:])
    assert len(bodies) == 2
    follow = bodies[1]["input"]
    assert follow[-1]["type"] == "function_call_output"
    assert follow[-1]["call_id"] == "call_1"
    assert follow[-1]["output"] == "wrote draft-0.txt"
    assert follow[-2]["type"] == "function_call"


def test_responses_request_sends_tools_when_present():
    tool = sandbox_write_tool()
    req = _responses_request(
        base_url="https://example.test/v1",
        api_key="sk-test",
        model="gpt-test",
        effort="none",
        instructions="instr",
        user="q",
        stream=True,
        tools=[tool],
    )
    body = json.loads(req.data.decode("utf-8"))
    assert body["tools"] == [tool]
    assert body["tool_choice"] == "auto"
    assert body["background"] is False


def test_responses_request_never_sets_background():
    req = _responses_request(
        base_url="https://example.test/v1",
        api_key="sk-test",
        model="gpt-test",
        effort="none",
        instructions="instr",
        user="q",
        stream=False,
    )
    body = json.loads(req.data.decode("utf-8"))
    assert body["background"] is False


def test_live_llm_requires_key():
    llm = LiveLlm(user_prompt="q", api_key="")
    with pytest.raises(LiveLlmError, match="missing"):
        llm.generate()
