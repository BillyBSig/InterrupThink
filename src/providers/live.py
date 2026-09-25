from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

STEP_INSTRUCTIONS = """You are a specialist. Write checkable thought as ordinary sentences.
Do not use XML or step tags.
When the work is finished, put the outcome on its own line starting with "answer: ".
Do not use hidden reasoning as the team channel."""

TOOL_INSTRUCTIONS = """You are a specialist. Perform every file write by calling the write tool.
Never say a file was written unless you already called the write tool for that exact path in this conversation. If a corrected path replaces an earlier one, call the write tool again for the corrected path before answering.
State checkable thought as ordinary sentences. Do not use XML or step tags.
When the work is finished, put the outcome on its own line starting with "answer: ".
Do not use hidden reasoning as the team channel."""


class LiveLlmError(RuntimeError):
    """The provider call failed, or the caller has no API key.

    The message includes the HTTP status when the provider rejected the
    request. It does not include the API key.
    """


class LiveLlm:
    """Live specialist via an OpenAI Responses-compatible endpoint.

    The default base URL is the OpenAI API. ``LLM_BASE_URL`` selects
    another endpoint that accepts the same request shape. Streaming runs
    in the foreground. ``abort`` closes that stream and posts cancel.
    ``cancel_ok`` records the HTTP result; it does not prove the provider
    stopped generating.

    Attributes:
        user_prompt: Task text for this specialist. The session does not
            rewrite it.
        model: Model name. Defaults to ``LLM_MODEL`` or ``gpt-5.6-luna``.
        effort: Reasoning effort sent to the provider.
        api_key: Key from the constructor, ``LLM_API_KEY``, or
            ``OPENAI_API_KEY``.
        base_url: API root, without a trailing slash.
        timeout_s: Socket timeout for the streaming request.
        prefix: Resume text stored by ``apply_resume``.
        tokens_emitted: Rough count of text yielded to the caller.
        tokens_wasted: Rough count charged by ``abort``.
        aborted: Whether ``abort`` was called during the current request.
        last_usage: Usage object from the completed response, if any.
        response_id: Provider response id for the current stream.
        cancel_ok: Whether the cancel HTTP call reported success.
    """

    def __init__(
        self,
        *,
        user_prompt: str,
        model: str | None = None,
        effort: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_s: float = 90.0,
        tools: list | None = None,
    ) -> None:
        """Store the prompt and the provider settings.

        Args:
            user_prompt: Task text. A later resume prefix is appended to
                it and does not replace it.
            model: Model name. Defaults to ``LLM_MODEL`` or
                ``gpt-5.6-luna``.
            effort: Reasoning effort. Defaults to ``LLM_REASONING_EFFORT``
                or ``"none"``.
            api_key: Bearer token. Defaults to ``LLM_API_KEY`` or
                ``OPENAI_API_KEY``.
            base_url: API root. Defaults to ``LLM_BASE_URL`` or the
                OpenAI API.
            timeout_s: Socket timeout for the streaming request.
            tools: Native function tools. Empty leaves the text channel
                unchanged. A write call is yielded as one tool step.
        """
        self.user_prompt = user_prompt
        self.model = model or os.environ.get("LLM_MODEL", "gpt-5.6-luna")
        self.effort = effort or os.environ.get("LLM_REASONING_EFFORT", "none")
        self.api_key = api_key or os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.timeout_s = timeout_s
        self.prefix: str | None = None
        self.tokens_emitted = 0
        self.tokens_wasted = 0
        self.aborted = False
        self.last_usage: dict = {}
        self.response_id: str | None = None
        self.cancel_ok = False
        self.tools = list(tools or [])
        self._stream = None
        self._request_tokens = 0
        self._tool_names: dict[str, str] = {}
        self._tool_call_ids: dict[str, str] = {}
        self._tool_bufs: dict[str, str] = {}
        self._tool_done: set[str] = set()
        self._pending_call: dict | None = None
        self._tool_result: str | None = None
        self._transcript: list = []

    def generate(self) -> str:
        """Return the specialist document for this request.

        Returns:
            The streamed text joined into one string.

        Raises:
            LiveLlmError: No API key is configured, or the provider
                returns an HTTP error.
        """
        return "".join(self.iter_deltas())

    def iter_deltas(self):
        """Stream the specialist document for this request.

        The request sets ``background`` false, so generation runs in the
        foreground. ``abort`` stops the iteration and closes the stream.

        Yields:
            Text deltas from the provider.

        Raises:
            LiveLlmError: No API key is configured, or the provider
                returns an HTTP error.
        """
        if not self.api_key:
            raise LiveLlmError("missing OPENAI_API_KEY or LLM_API_KEY")
        self.aborted = False
        self.response_id = None
        self._request_tokens = 0
        self._tool_names = {}
        self._tool_call_ids = {}
        self._tool_bufs = {}
        self._tool_done = set()
        self._pending_call = None
        self._tool_result = None
        user = self.user_prompt
        if self.prefix:
            user = f"{self.user_prompt}\n\nResume prefix (do not repeat dropped text):\n{self.prefix}"
        self._transcript = [{"role": "user", "content": user}]
        for _round in range(4):
            if self.aborted:
                break
            yield from self._stream_round(self._transcript)
            if self.aborted or self._tool_result is None or self._pending_call is None:
                break
            call = self._pending_call
            output = self._tool_result
            self._pending_call = None
            self._tool_result = None
            self._transcript.append(
                {
                    "type": "function_call",
                    "call_id": call["call_id"],
                    "name": call["name"],
                    "arguments": call["arguments"],
                }
            )
            self._transcript.append(
                {
                    "type": "function_call_output",
                    "call_id": call["call_id"],
                    "output": output,
                }
            )

    def submit_tool_result(self, output: str) -> None:
        """Store the host's tool result for the next model turn.

        Args:
            output: Text returned by the executed tool.
        """
        self._tool_result = output

    def _stream_round(self, model_input):
        """Stream one provider turn.

        Args:
            model_input: User string or the running tool transcript.

        Yields:
            Text deltas and one tool step when a function call completes.
            After a tool step, iteration returns so the host can submit
            the tool result.
        """
        req = _responses_request(

            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            effort=self.effort,
            instructions=TOOL_INSTRUCTIONS if self.tools else STEP_INSTRUCTIONS,
            user=model_input,
            stream=True,
            tools=self.tools,
        )
        try:
            stream = urllib.request.urlopen(req, timeout=self.timeout_s)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise LiveLlmError(f"HTTP {exc.code}: {detail}") from exc
        self._stream = stream
        try:
            for event in _iter_sse(stream):
                if self.aborted:
                    break
                etype = event.get("type") or ""
                if etype == "response.created":
                    resp = event.get("response") or {}
                    if isinstance(resp, dict):
                        self.response_id = resp.get("id") or self.response_id
                elif etype == "response.output_text.delta":
                    delta = event.get("delta")
                    if isinstance(delta, str) and delta:
                        n = max(1, len(delta.split()))
                        self._request_tokens += n
                        self.tokens_emitted += n
                        yield delta
                else:
                    step = self._native_tool_step(event)
                    if step:
                        yield step
                        return
                if etype == "response.completed":
                    resp = event.get("response") or {}
                    usage = resp.get("usage") if isinstance(resp, dict) else {}
                    if isinstance(usage, dict):
                        self.last_usage = usage
                        out_tokens = int(usage.get("output_tokens") or 0)
                        if out_tokens:
                            self.tokens_emitted = max(self.tokens_emitted, out_tokens)
        except (OSError, ValueError):
            if not self.aborted:
                raise
        finally:
            self._close_stream()


    def _native_tool_step(self, event: dict) -> str | None:
        """Buffer one function-call stream and yield it once when complete.

        Args:
            event: One server-sent event from the Responses stream.

        Returns:
            A tool step after the arguments are complete. ``None`` while
            the call is still streaming, or when this call was already
            yielded.
        """
        etype = event.get("type") or ""
        if etype == "response.output_item.added":
            item = event.get("item") or {}
            if isinstance(item, dict) and item.get("type") == "function_call":
                item_id = str(item.get("id") or item.get("call_id") or "")
                if item_id:
                    self._tool_names[item_id] = str(item.get("name") or "")
                    self._tool_call_ids[item_id] = str(item.get("call_id") or item_id)
                    self._tool_bufs.setdefault(item_id, str(item.get("arguments") or ""))
            return None
        if etype == "response.function_call_arguments.delta":
            item_id = str(event.get("item_id") or "")
            if item_id:
                self._tool_bufs[item_id] = self._tool_bufs.get(item_id, "") + str(event.get("delta") or "")
            return None
        if etype == "response.function_call_arguments.done":
            item_id = str(event.get("item_id") or "")
            name = str(event.get("name") or self._tool_names.get(item_id) or "")
            arguments = str(event.get("arguments") or self._tool_bufs.get(item_id) or "")
            return self._finish_tool(item_id, name, arguments)
        if etype == "response.output_item.done":
            item = event.get("item") or {}
            if isinstance(item, dict) and item.get("type") == "function_call":
                item_id = str(item.get("id") or item.get("call_id") or "")
                name = str(item.get("name") or self._tool_names.get(item_id) or "")
                arguments = str(item.get("arguments") or self._tool_bufs.get(item_id) or "")
                return self._finish_tool(item_id, name, arguments)
        return None

    def _finish_tool(self, item_id: str, name: str, arguments: str) -> str | None:
        """Emit one completed function call and ignore a second notice.

        Args:
            item_id: Provider item id. Empty ids are ignored.
            name: Function name.
            arguments: JSON object string.

        Returns:
            The tool step, or ``None`` only when this call id was already
            emitted. Malformed arguments still return a step (a safe
            fallback claim), so a completed call is never dropped.
        """
        if not item_id or item_id in self._tool_done:
            return None
        self._pending_call = {
            "call_id": self._tool_call_ids.get(item_id, item_id),
            "name": name,
            "arguments": arguments,
        }
        step = tool_call_step(name, arguments)
        if step is None:
            return None
        self._tool_done.add(item_id)
        count = max(1, len(step.split()))
        self._request_tokens += count
        self.tokens_emitted += count
        return step

    def abort(self) -> None:
        """Close the stream and post cancel.

        ``cancel_ok`` records whether that HTTP call succeeded. It is not
        proof that the provider stopped generating.
        """
        self.aborted = True
        wasted = max(1, self._request_tokens)
        self._close_stream()
        if self.response_id and self.api_key:
            self.cancel_ok = _cancel_response(self.base_url, self.api_key, self.response_id)
        self.tokens_wasted += wasted

    def apply_resume(self, envelope: str | None) -> None:
        """Store the resume prefix for the next request.

        The next stream sends the original prompt plus this prefix. The
        provider cache is not rewound.

        Args:
            envelope: Resume text from the floor. ``None`` clears it.
        """
        self.prefix = envelope or None

    def _close_stream(self) -> None:
        """Close the current response stream, ignoring a second close."""
        stream = self._stream
        self._stream = None
        if stream is None:
            return
        try:
            stream.close()
        except OSError:
            pass


def load_dotenv(path: str | Path = ".env") -> None:
    """Load environment variables that are not already set.

    Args:
        path: File of ``KEY=value`` lines. Missing files are ignored.
            Blank lines and ``#`` comments are skipped.
    """
    env_path = Path(path)
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))



def sandbox_write_tool() -> dict:
    """Return the Responses schema for the sandbox write tool.

    The host still executes ``SandboxWriteTool``. This schema is what a
    current model calls. The stream adapter turns that call into one
    tool step for the floor.

    Returns:
        One function tool with a strict object schema.
    """
    return {
        "type": "function",
        "name": "write",
        "description": "Write one file. path is the relative file name. content is the file text.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file name."},
                "content": {"type": "string", "description": "File text."},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        "strict": True,
    }


def tool_call_step(name: str, arguments: str) -> str:
    """Turn one native function call into a tool step.

    A leading newline guarantees this line starts on its own; the plain
    text channel has no tag to mark a boundary, so a delta arriving right
    after an unterminated text line would otherwise fuse onto it.

    Args:
        name: Function name from the provider.
        arguments: JSON object string. An empty string is an empty object.

    Returns:
        One tool step the floor already parses. A malformed or nameless
        call still returns a step, as a claim describing the raw call, so
        a completed function-call event never yields nothing (a request
        with zero steps raises ``ValueError`` in the session).
    """
    try:
        args = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError:
        args = None
    if not name or not isinstance(args, dict):
        raw = arguments.replace("\n", " ")
        return f"\nclaim: malformed tool call {name!r} args={raw!r}\n"
    body = json.dumps({"name": name, "args": args}, ensure_ascii=False)
    return f"\ntool_intent: {body}\n"


def _responses_request(
    *,
    base_url: str,
    api_key: str,
    model: str,
    effort: str,
    instructions: str,
    user: str,
    stream: bool,
    tools: list | None = None,
) -> urllib.request.Request:
    """Build a streaming or blocking Responses request.

    Args:
        base_url: API root, without a trailing slash.
        api_key: Bearer token.
        model: Model name.
        effort: Reasoning effort.
        instructions: System text for the specialist.
        user: User text, including a resume prefix when one is stored.
        stream: Whether the response should be server-sent events.

    Returns:
        A POST request for ``/responses``. ``background`` is false.
    """
    body = {
        "model": model,
        "reasoning": {"effort": effort},
        "instructions": instructions,
        "input": user,
        "stream": stream,
        "background": False,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    return urllib.request.Request(
        f"{base_url}/responses",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if stream else "application/json",
        },
    )


def _cancel_response(base_url: str, api_key: str, response_id: str) -> bool:
    """Post a cancel for one response.

    Args:
        base_url: API root.
        api_key: Bearer token.
        response_id: Provider id captured from the stream.

    Returns:
        True when the HTTP call succeeds or the payload says the response
        is cancelled or completed. False on a network or HTTP error.
        Success here does not prove generation stopped.
    """
    req = urllib.request.Request(
        f"{base_url}/responses/{response_id}/cancel",
        method="POST",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8") or "{}"
            code = getattr(resp, "status", 200)
        payload = json.loads(raw) if raw.strip().startswith("{") else {}
        status = payload.get("status") if isinstance(payload, dict) else None
        return status in {"cancelled", "completed"} or code < 300
    except urllib.error.HTTPError as exc:
        _ = exc.read()[:300]
        return False
    except OSError:
        return False
    except json.JSONDecodeError:
        return False


def _iter_sse(stream):
    """Yield JSON events from a server-sent event stream.

    Args:
        stream: Readable response body.

    Yields:
        One dictionary per ``data:`` event. ``[DONE]`` ends the stream.
        A line that is not JSON is skipped.
    """
    data_lines: list[str] = []
    while True:
        raw = stream.readline()
        if not raw:
            break
        line = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
        line = line.rstrip("\r\n")
        if line.startswith("data:"):
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            data_lines.append(payload)
            continue
        if line == "" and data_lines:
            blob = "\n".join(data_lines)
            data_lines = []
            try:
                event = json.loads(blob)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                yield event
    if data_lines:
        try:
            event = json.loads("\n".join(data_lines))
        except json.JSONDecodeError:
            return
        if isinstance(event, dict):
            yield event


def _output_text(payload: dict) -> str:
    """Read the assistant text from a Responses payload.

    Args:
        payload: JSON object returned by the provider.

    Returns:
        ``output_text`` when it is present. Otherwise the text parts of
        message output. An empty string when neither is present.
    """
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct
    chunks: list[str] = []
    for item in payload.get("output") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        for part in item.get("content") or []:
            if isinstance(part, dict) and part.get("type") in {"output_text", "text"}:
                text = part.get("text")
                if isinstance(text, str):
                    chunks.append(text)
    return "".join(chunks)


def _strip_fences(text: str) -> str:
    """Remove one surrounding markdown fence.

    Args:
        text: Provider text that may start with a fence.

    Returns:
        The text without that fence.
    """
    stripped = text.strip()
    stripped = re.sub(r"^```(?:xml)?\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()
