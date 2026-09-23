# Integrations

[English](integrations.md) · [Bahasa Indonesia](id/integrations.md)

InterrupThink integrates at the host boundary. A framework may provide
messages, nodes, agents, tasks, or retrieval; the semantic thinking floor
remains `run_session`.

Optional frameworks are not core dependencies. Install them in an isolated
environment with `pip` when running a specific example. The default library
installation and test suite must remain usable without them.

## Native Python host

The native pattern is the reference integration:

```python
from interrupthink import LlmMonitor, run_session

result = run_session(llm=specialist_llm, monitor=LlmMonitor(), tool=tool)
```

For a two-specialist pipeline, the host runs one session for retrieval and
starts the writer session only when the first session is allowed to continue.
The host forwards approved context; it does not create a symmetric
specialist-to-specialist interrupt channel.

See [`../cases/two-specialists/`](../cases/two-specialists/).

## LangGraph

Put `run_session` in the agent or specialist node and keep the host graph and
`ToolNode` at their normal boundary. The graph's tool-boundary interrupt can
remain a second line of defense, but it is not the semantic reasoning floor.

```bash
pip install langgraph
python3 cases/langgraph-apply/run.py
python3 cases/langgraph-correct/run.py
```

See [`../cases/langgraph-node/`](../cases/langgraph-node/) for a host test,
[`../cases/langgraph-apply/`](../cases/langgraph-apply/) for the 1:1
`ToolNode` freeze example, and
[`../cases/langgraph-correct/`](../cases/langgraph-correct/) for correct-then-continue.

## LangChain

Use LangChain for the prompt, message history, or tool wrapper, and call
`run_session` for the thinking slot. The example does not use
`AgentExecutor` as a replacement for the floor.

```bash
pip install langchain
python3 cases/langchain-specialist/run.py
python3 cases/langchain-correct/run.py
python3 cases/langchain-chat/run.py
```

See [`../cases/langchain-specialist/`](../cases/langchain-specialist/),
[`../cases/langchain-correct/`](../cases/langchain-correct/), and
[`../cases/langchain-chat/`](../cases/langchain-chat/).

## LlamaIndex

Use the framework's retriever for retrieval and pass its result into the
session. The current example uses `VectorStoreIndex.as_retriever().retrieve`;
the framework `QueryEngine` is not used as the thinking loop.

```bash
pip install llama-index llama-index-llms-openai
python3 cases/llamaindex-retrieve/run.py
```

See [`../cases/llamaindex-retrieve/`](../cases/llamaindex-retrieve/).

## CrewAI

CrewAI can label one role or two sequential roles with `Agent`, `Task`, and
`Crew`. `run_session` remains the think loop. `Crew.kickoff` is not used as a
replacement for the floor, and the examples do not enable hierarchical
delegation.

```bash
pip install crewai
python3 cases/crewai-pipe/run.py
python3 cases/crewai-correct/run.py
```

See [`../cases/crewai-pipe/`](../cases/crewai-pipe/) and
[`../cases/crewai-correct/`](../cases/crewai-correct/).

## AutoGen

AutoGen can label one `ConversableAgent` or two sequential roles. The current
examples set `human_input_mode="NEVER"` and call `run_session` for the think
slot. They do not use `initiate_chat` as the thinking loop or `UserProxyAgent`
as the semantic interrupt mechanism.

```bash
pip install autogen
python3 cases/autogen-pipe/run.py
python3 cases/autogen-correct/run.py
```

See [`../cases/autogen-pipe/`](../cases/autogen-pipe/) and
[`../cases/autogen-correct/`](../cases/autogen-correct/).

## Named handoffs inside a framework

The framework keeps its nodes, roles, messages, or index. `run_session` still judges the specialist. When the result names a receiver, the host composes `Escalation`, `Consult`, or `Takeover` and opens the next step. The framework's own handoff, delegation, chat engine, or group chat does not make that choice.

| Host | Route | What the folder shows |
|---|---|---|
| LangGraph | Escalation | [`cases/langgraph-offer/`](../cases/langgraph-offer/): the dealer node checks a listed price; the policy node receives the package; the one-dollar offer is not committed |
| LangChain | Consultation | [`cases/langchain-rule/`](../cases/langchain-rule/): the checker receives the posted rule; the patch returns to the same chat |
| CrewAI | Escalation | [`cases/crewai-order/`](../cases/crewai-order/): the counter role receives the order package; `place_order` does not run |
| AutoGen | Takeover to `human` | [`cases/autogen-support/`](../cases/autogen-support/): the human receives the package; no second agent continues |
| LlamaIndex | Consultation | [`cases/llamaindex-page/`](../cases/llamaindex-page/): the checker receives one retrieved page; the same assistant continues only as far as that page |

Each folder owns its route. The short call sites live under [`examples/`](../examples/). Install the framework in a virtual environment when you run that folder. Do not add it to the core package.

## Integration boundary

The integration examples demonstrate wiring, not framework replacement. They
do not claim that InterrupThink inherits the framework's reliability,
observability, persistence, or deployment guarantees.

The session result carries a prefix and watermarks. The host stores those in
its own checkpointer or queue. InterrupThink stays a 1:1 floor inside the
process that called `run_session`. It does not import a graph checkpointer
and it does not recover a crashed process.
