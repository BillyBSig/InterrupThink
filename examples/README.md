# Examples — module call sites

After `pip install -e .`, these files show **how to call** `interrupthink` / `src`. They are not full use-case solutions.

Every file below calls `LiveLlm` and needs a personal API key in a local
`.env` file (never committed). For deterministic, no-key call sites, see
[`dummy/`](dummy/).

Three call sites name a receiver while the verdict stays `Ok`. Escalation
(`escalate_to`) gives the package to the next specialist. Consultation
(`consult_to`) returns a patch to the same specialist. Takeover
(`takeover_to`) gives the package to an editor or a human. `Escalation`,
`Consult`, and `Takeover` compose that text and do not start the next
session. The folders under [`cases/`](../cases/) are the runnable stories.

Solutions (ticket, sandbox, `tmp/` / `runs/` traces): [`cases/`](../cases/).

| File | Calls | Scenario |
|------|-------|----------|
| [`citation_consult.py`](citation_consult.py) | host + `LiveLlm` | A citation checker returns a patch and the same drafter continues |
| [`fare_escalation.py`](fare_escalation.py) | host + `LiveLlm` | A policy specialist receives the fare result and the front agent stops |
| [`database_takeover.py`](database_takeover.py) | host + `LiveLlm` | A human receives the blocked-delete package and the agent does not resume |
| [`staging_migrate_live.py`](staging_migrate_live.py) | `LiveLlm` + paired seeds | Live smoke check for the dummy staging-migration story |
| [`langchain_specialist.py`](langchain_specialist.py) | `run_session` + `LiveLlm` | Check a release-freeze claim before a LangChain file write |
| [`langchain_correct.py`](langchain_correct.py) | `run_session` + `LiveLlm` | Correct a wrong deployment host and continue with LangChain |
| [`langchain_chat.py`](langchain_chat.py) | `run_session` per chat turn | Check a support-policy claim before publishing an answer |
| [`langchain_rule_consult.py`](langchain_rule_consult.py) | LangChain chat + `LiveLlm` | The same chat continues after a checker returns the rule |
| [`langgraph_specialist_node.py`](langgraph_specialist_node.py) | `run_session` in one LangGraph node | Stop a hotfix write when the release-freeze claim is wrong |
| [`langgraph_apply.py`](langgraph_apply.py) | `run_session` + `ToolNode` | Add the thinking check to an existing LangGraph tool workflow |
| [`langgraph_correct.py`](langgraph_correct.py) | `run_session` + `ToolNode` | Correct a deployment host and continue to the staging write |
| [`langgraph_two_specialists.py`](langgraph_two_specialists.py) | Two LangGraph nodes | Review retrieved policy information before creating a decision |
| [`langgraph_offer_escalation.py`](langgraph_offer_escalation.py) | Two LangGraph nodes + `LiveLlm` | A policy node receives the offer package and the dealer chat stops |
| [`llamaindex_retrieve_node.py`](llamaindex_retrieve_node.py) | `run_session` + LlamaIndex retriever | Check a retrieved policy document before writing a notice |
| [`llamaindex_page_consult.py`](llamaindex_page_consult.py) | LlamaIndex retriever + `LiveLlm` | The same assistant continues only as far as the retrieved page |
| [`crewai_two_specialists.py`](crewai_two_specialists.py) | Two CrewAI roles | Review policy information before a second role creates a decision |
| [`crewai_order_escalation.py`](crewai_order_escalation.py) | Two CrewAI roles + `LiveLlm` | The counter role receives the order package and the wrong order is not placed |
| [`crewai_correct.py`](crewai_correct.py) | `run_session` in one CrewAI role | Correct a deployment host and continue with CrewAI |
| [`autogen_two_specialists.py`](autogen_two_specialists.py) | Two AutoGen agents | Review policy information before a second agent creates a decision |
| [`autogen_support_takeover.py`](autogen_support_takeover.py) | One AutoGen agent + `LiveLlm` | A human receives the support package and no second agent continues |
| [`autogen_correct.py`](autogen_correct.py) | `run_session` in one AutoGen agent | Correct a deployment host and continue with AutoGen |

Deterministic, no-API-key call sites (`FakeLlm`, `DummyTool`) live in
[`dummy/`](dummy/), not in this list.
