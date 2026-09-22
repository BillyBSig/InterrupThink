# Examples — module call sites

After `pip install -e .`, these files show **how to call** `interrupthink` / `src`. They are not full use-case solutions.

Solutions (ticket, sandbox, `tmp/` / `runs/` traces): [`cases/`](../cases/).

| File | Calls | Scenario |
|------|-------|----------|
| [`run_session_dummy.py`](run_session_dummy.py) | `run_session` | Stop an unsafe planned action using deterministic local components |
| [`staging_migrate.py`](staging_migrate.py) | Local staging-migration helper | Prevent a migration to production when the ticket host is staging |
| [`langchain_specialist.py`](langchain_specialist.py) | `run_session` + `LiveLlm` | Check a release-freeze claim before a LangChain file write |
| [`langchain_correct.py`](langchain_correct.py) | `run_session` + `LiveLlm` | Correct a wrong deployment host and continue with LangChain |
| [`langchain_chat.py`](langchain_chat.py) | `run_session` per chat turn | Check a support-policy claim before publishing an answer |
| [`langgraph_specialist_node.py`](langgraph_specialist_node.py) | `run_session` in one LangGraph node | Stop a hotfix write when the release-freeze claim is wrong |
| [`langgraph_apply.py`](langgraph_apply.py) | `run_session` + `ToolNode` | Add the thinking check to an existing LangGraph tool workflow |
| [`langgraph_correct.py`](langgraph_correct.py) | `run_session` + `ToolNode` | Correct a deployment host and continue to the staging write |
| [`langgraph_two_specialists.py`](langgraph_two_specialists.py) | Two LangGraph nodes | Review retrieved policy information before creating a decision |
| [`llamaindex_retrieve_node.py`](llamaindex_retrieve_node.py) | `run_session` + LlamaIndex retriever | Check a retrieved policy document before writing a notice |
| [`crewai_two_specialists.py`](crewai_two_specialists.py) | Two CrewAI roles | Review policy information before a second role creates a decision |
| [`crewai_correct.py`](crewai_correct.py) | `run_session` in one CrewAI role | Correct a deployment host and continue with CrewAI |
| [`autogen_two_specialists.py`](autogen_two_specialists.py) | Two AutoGen agents | Review policy information before a second agent creates a decision |
| [`autogen_correct.py`](autogen_correct.py) | `run_session` in one AutoGen agent | Correct a deployment host and continue with AutoGen |

Older dummy files (`*_dummy.py`, `host_loop_dummy.py`, and
`staging_migrate_live.py`) are local call sites for learning and regression
checks. They are not full use-case solutions.
