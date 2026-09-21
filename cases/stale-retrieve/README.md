# Checking retrieved information before acting

This example shows a common retrieval problem: a system finds an old policy
document and then wants to use it to write a customer notice. The specialist
must first describe what it found. If it claims that the old document is
current, the supervisor interrupts the session and the notice is not written.

Everything runs against local fixture files. There is no vector database or
external messaging service, so the example is easy to run and inspect.

From the repo root:

```bash
uv pip install -e .
python3 cases/stale-retrieve/run.py
```

The policy fixtures are shared with the two-specialist example. This case does
not require Qdrant, Atlas, Chroma, or another external database.
