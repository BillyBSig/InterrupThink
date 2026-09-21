from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

STEP_INSTRUCTIONS = """You are a specialist. Emit ONLY XML (no markdown fences, no prose outside tags).
Use this shape, at least one <step> and one <answer>:
<step kind="plan">...</step>
<step kind="premise">...</step>
<step kind="claim">...</step>
<answer>...</answer>
kind whitelist: plan, premise, claim, evidence, tool_intent, doubt, answer_draft.
Do not use hidden reasoning as the team channel; put checkable thought in <step> tags."""


class LiveLlmError(RuntimeError):
    """Provider call failed or returned empty text."""


class LiveOpenAILlm:
    """Live specialist model via the OpenAI Responses API."""

    def __init__(
        self,
        *,
        user_prompt: str,
        model: str | None = None,
        effort: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_s: float = 90.0,
    ) -> None:
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
        self._stream = None
        self._request_tokens = 0

    def generate(self) -> str:
        return "".join(self.iter_deltas())

    def iter_deltas(self):
        if not self.api_key:
            raise LiveLlmError("missing OPENAI_API_KEY or LLM_API_KEY")
        self.aborted = False
        self.response_id = None
        self._request_tokens = 0
        user = self.user_prompt
        if self.prefix:
            user = f"{self.user_prompt}\n\nResume prefix (do not repeat dropped text):\n{self.prefix}"
        req = _responses_request(
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            effort=self.effort,
            instructions=STEP_INSTRUCTIONS,
            user=user,
            stream=True,
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
                elif etype == "response.completed":
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

    def abort(self) -> None:
        """Close the stream and POST cancel. ``cancel_ok`` is HTTP wiring, not a stop proof."""
        self.aborted = True
        wasted = max(1, self._request_tokens)
        self._close_stream()
        if self.response_id and self.api_key:
            self.cancel_ok = _cancel_response(self.base_url, self.api_key, self.response_id)
        self.tokens_wasted += wasted

    def apply_resume(self, envelope: str | None) -> None:
        self.prefix = envelope or None

    def _close_stream(self) -> None:
        stream = self._stream
        self._stream = None
        if stream is None:
            return
        try:
            stream.close()
        except OSError:
            pass


def load_dotenv(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _responses_request(
    *,
    base_url: str,
    api_key: str,
    model: str,
    effort: str,
    instructions: str,
    user: str,
    stream: bool,
) -> urllib.request.Request:
    body = {
        "model": model,
        "reasoning": {"effort": effort},
        "instructions": instructions,
        "input": user,
        "stream": stream,
        "background": False,
    }
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
    stripped = text.strip()
    stripped = re.sub(r"^```(?:xml)?\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()
