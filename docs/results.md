# Results

[English](results.md) · [Bahasa Indonesia](id/results.md)

This page is a public summary of the current contract evidence. It is
deliberately narrower than a product benchmark: each result describes a
fixture, a control path, and a protected side effect.

Two contracts appear throughout: **block** a bad side effect, and **correct**
the reasoning process then **continue** (rollback). Cancellation without a
resume path is not the intended default.

## Summary

### Native two-session pipeline

- **Method:** deterministic `FakeLlm` and scripted monitor; one retrieval
  session followed by a conditional writer session.
- **Observed result:** a stale retrieval claim is interrupted before the writer
  starts; the clean control path runs two sessions and creates one decision
  file.
- **Evidence:** `tests/test_two_specialists.py`,
  `cases/two-specialists/`.
- **Limit:** the retrieval data is a local fixture, not a production vector
  database or a live knowledge base.

### Sandbox write guard

- **Method:** deterministic session with a real file-system sandbox.
- **Observed result:** an interrupted path creates no file; the allowed path
  writes one file inside the sandbox; a traversal outside the sandbox is
  rejected.
- **Evidence:** `tests/test_sandbox_write.py`,
  `cases/freeze-write/`.
- **Limit:** the sandbox is not a security boundary for an untrusted process.

### Correct and resume

- **Method:** deterministic two-request session with a corrected premise.
- **Observed result:** the incorrect production file is absent, the resume
  event records `rollback`, and the corrected staging file can be written.
- **Evidence:** `tests/test_correct_resume.py`,
  `cases/correct-resume/`,
  `tests/test_langchain_correct.py`,
  `cases/langchain-correct/`,
  `tests/test_langgraph_correct.py`,
  `cases/langgraph-correct/`,
  `tests/test_crewai_correct.py`,
  `cases/crewai-correct/`,
  `tests/test_autogen_correct.py`,
  `cases/autogen-correct/`.
- **Limit:** the example verifies the floor's watermark and request flow; it
  does not provide general checkpoint durability or process recovery.

### Deny-answer pipeline

- **Method:** deterministic host with an answer session and a downstream
  outbox session.
- **Observed result:** an interrupted policy claim does not reach the outbox;
  the allowed control path writes one bounded line.
- **Evidence:** `tests/test_false_policy.py`,
  `tests/test_deny_answer_pipeline.py`,
  `cases/deny-answer-pipeline/`.
- **Limit:** the outbox is a local file, not an email or messaging provider.

### LangGraph host

- **Method:** optional-package tests with a specialist node calling
  `run_session` and a normal `ToolNode`.
- **Observed result:** interruption can skip a protected ToolNode write, and
  it can **correct** a wrong host claim then continue so ToolNode writes
  `staging.txt` instead of `production.txt`.
- **Evidence:** `tests/test_langgraph_node.py`,
  `tests/test_langgraph_apply.py`,
  `tests/test_langgraph_correct.py`,
  `cases/langgraph-node/`, `cases/langgraph-apply/`,
  `cases/langgraph-correct/`.
- **Limit:** the framework is tested as a host wiring pattern, not replaced or
  benchmarked.

### LangChain host

- **Method:** optional-package tests for a 1:1 specialist, a two-turn chat
  history, and a correct-then-continue wrapper.
- **Observed result:** interruption can block a protected write or unsupported
  answer, and it can **correct** a wrong host claim then continue (rollback)
  so the staging file is written instead of production.
- **Evidence:** `tests/test_langchain_extra.py`,
  `tests/test_langchain_chat.py`,
  `tests/test_langchain_correct.py`,
  `cases/langchain-specialist/`, `cases/langchain-chat/`,
  `cases/langchain-correct/`.
- **Limit:** the tests use injected deterministic doubles; they do not
  evaluate a model's conversational quality.

### LlamaIndex retrieval

- **Method:** optional-package test with `VectorStoreIndex`, a deterministic
  embedding, and `as_retriever().retrieve`.
- **Observed result:** a stale retrieved chunk is interrupted before
  `notice.txt`; the current control path retrieves and writes one notice.
- **Evidence:** `tests/test_llamaindex_extra.py`,
  `cases/llamaindex-retrieve/`.
- **Limit:** the index contains one test document; no external vector store is
  evaluated.

### CrewAI and AutoGen hosts

- **Method:** optional-package tests with sequential host roles, while each
  thinking slot calls `run_session`. CrewAI and AutoGen also have a 1:1
  correct-then-continue wrapper.
- **Observed result:** stale input stops the writer before `decision.txt`;
  current input runs two sessions and creates one decision file. On the 1:1
  path, a wrong host claim is patched and `staging.txt` is written instead of
  `production.txt`.
- **Evidence:** `tests/test_crewai_extra.py`,
  `tests/test_autogen_extra.py`,
  `tests/test_crewai_correct.py`,
  `tests/test_autogen_correct.py`,
  `cases/crewai-pipe/`, `cases/autogen-pipe/`,
  `cases/crewai-correct/`, `cases/autogen-correct/`.
- **Limit:** the framework objects are host labels and containers in this
  experiment. This does not evaluate hierarchical orchestration, group chat,
  delegation quality, or framework production behavior.

### Named handoffs

- **Method:** deterministic sessions. The monitor returns `Ok` and a
  receiver name. `Escalation`, `Consult`, and `Takeover` compose the
  package from the floor event. Optional-framework folders repeat the
  same package shape inside one host each.
- **Observed result:** the unfinished answer is not committed. The package
  keeps the original task, the receiver, the supervisor reason, the kept
  steps, recorded tool results, and the calls that must not be repeated.
  Escalation does not resume the first specialist. Consultation returns a
  patch to the same specialist. A human takeover returns the package and
  does not start a second specialist.
- **Evidence:** `tests/test_supervisor_escalation.py`,
  `tests/test_supervisor_consult.py`,
  `tests/test_supervisor_takeover.py`,
  `tests/test_supervisor_handoff.py`,
  `cases/langgraph-offer/`,
  `cases/langchain-rule/`,
  `cases/crewai-order/`,
  `cases/autogen-support/`,
  `cases/llamaindex-page/`.
- **Limit:** the scripted documents lock the contract. A live run can show
  that a session started and a package arrived. Its wording is not the
  referee.

### Supervisor output and neutral core

- **Method:** deterministic monitor and runtime tests.
- **Observed result:** strict JSON-shaped supervisor output is accepted,
  malformed or unknown status values become `Unknown`, and the neutral
  runtime core carries no lab-specific defaults. The specialist step channel
  is plain labeled lines (`plan:`, `claim:`, `tool_intent:`, `answer:`); the
  parser still accepts the older `<step>`/`<answer>` XML shape so already
  recorded evidence stays reproducible.
- **Evidence:** `tests/test_llm_monitor.py`,
  `tests/test_run_session_contract.py`,
  `tests/test_spike_paths.py`.
- **Limit:** schema validation does not make a supervisor correct; it only
  makes malformed output fail closed to the neutral state.

### Packaging

- **Method:** local wheel build and installation from a clean working
  directory.
- **Observed result:** the `interrupthink` package can be imported from the
  local wheel without PyPI access.
- **Evidence:** `tests/test_wheel_install.py`,
  `tests/test_library_packaging.py`.
- **Limit:** this is a local packaging check, not a public release or a
  compatibility promise for every Python distribution.

## Interpretation

The evidence supports a reusable floor that can **interrupt**, **correct**,
and **continue** (rollback) across several host wiring patterns. It does not
establish that interruption improves accuracy, cost, latency, or user
experience. Those questions require separate experiments with a declared
baseline, dataset, model, metric, and uncertainty report.
