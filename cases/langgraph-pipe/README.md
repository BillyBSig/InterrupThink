# Passing reviewed information through LangGraph

This example uses a small `StateGraph` with two specialist nodes. The first
node retrieves a refund policy and the second node uses the reviewed result to
prepare a decision. Each node calls `run_session`, while the host graph owns
the handoff between them.

If the first specialist makes an unsupported claim, the graph stops there and
does not start the second specialist. This is a one-way handoff, not a
conversation in which the two specialists interrupt each other.

The policy fixtures are shared with `cases/two-specialists/`. This folder is a
host integration example, not a separate InterrupThink package.

```bash
pip install langgraph    # venv, not uv add
python3 cases/langgraph-pipe/run.py
```

Demo: `examples/langgraph_two_specialists.py`.
