# Getting started

[English](getting-started.md) · [Bahasa Indonesia](id/getting-started.md)

## Requirements

- Python 3.11 or newer
- `uv` or another tool that can create an isolated Python environment
- No API key for the deterministic examples

The source repository is currently the installation source. The package is not
published to PyPI.

## Install the library

From the source repository root:

```bash
uv pip install -e ".[dev]"
```

The core package has no framework-specific runtime dependency. Optional host
frameworks are installed separately when running their examples.

## Run the deterministic example

```bash
python3 examples/run_session_dummy.py
```

The example uses `FakeLlm`, `ScriptedMonitor`, and `DummyTool`. It demonstrates
**blocking**: with an interrupt, the irreversible publish call is not
executed; without an interrupt, the control path reaches the dummy tool.

That is only half of the floor. **Correction** is a second request after the
cut: the specialist continues from a watermark with a patched premise instead of restarting
the whole task. See [`cases/correct-resume/`](../cases/correct-resume/) and
`python3 cases/correct-resume/run.py`.

The tool records calls in memory; it does not publish anything.

## Compose a session

The public floor is composed from an LLM implementation, a monitor, and an
optional tool:

```python
from interrupthink import DummyTool, FakeLlm, ScriptedMonitor, run_session

wrong = """
<step kind="plan">publish the changelog</step>
<step kind="premise">the changelog is already approved</step>
<step kind="tool_intent" reversible="false">
{"name":"publish","args":{"doc":"changelog"}}
</step>
<answer>Published the changelog.</answer>
"""

stopped = """
<step kind="claim">the changelog is not approved</step>
<answer>Did not publish.</answer>
"""

tool = DummyTool()
result = run_session(
    llm=FakeLlm([wrong, stopped]),
    monitor=ScriptedMonitor(
        trigger_kind="premise",
        trigger_contains="already approved",
    ),
    tool=tool,
)

assert result.interrupt_ids
assert tool.calls == []
```

`run_session` asks the LLM for a second document after an interrupt. With
`FakeLlm`, that document must be present or the session raises `SessionError`.
This is deliberate: an interrupted request is aborted and resumed with a new
request rather than silently continuing the old request. A `Patch` can carry
replacement facts on that next request so the specialist continues the reasoning process
instead of only stopping. See [Concepts](concepts.md) and
[`cases/correct-resume/`](../cases/correct-resume/).

## Build a local wheel

The local wheel path is useful for checking installation from a clean working
directory:

```bash
uv build --wheel
uv pip install --offline --no-index dist/interrupthink-0.0.1-py3-none-any.whl
```

This is a local packaging check, not a release to PyPI.

## Run a case

The [`../cases/`](../cases/) directory contains sandboxed host examples. The
deterministic tests inject doubles; the command-line cases can use
`LiveOpenAILlm` with a personal environment file.

For example:

```bash
python3 cases/freeze-write/run.py
python3 cases/two-specialists/run.py
```

Do not commit credentials or generated files from `tmp/` and `runs/`.
