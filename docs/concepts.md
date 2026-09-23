# Concepts

[English](concepts.md) · [Bahasa Indonesia](id/concepts.md)

## The 1:1 thinking floor

InterrupThink separates the thinking loop from the host application. A
specialist produces a structured document; a monitor observes semantic steps;
the floor decides whether a tool call or answer can be committed.

The host may be a plain Python function or a framework graph. The host does
not replace the floor: each specialist slot still calls `run_session`.

```mermaid
flowchart LR
  specialist[Specialist] --> units[ThoughtUnit stream]
  units --> monitor[Monitor]
  monitor -->|Ok| commit[Commit approved output]
  monitor -->|Unknown| hold[Continue steps; hold answer]
  monitor -->|Patch| correct[Inject correction and resume]
  monitor -->|False| interrupt[Abort and request again]
  correct --> watermark[Resume with watermark]
  interrupt --> watermark
  watermark --> specialist
```

## ThoughtUnit boundaries

The interrupt boundary is a semantic `ThoughtUnit`, represented by a `<step>`
in the current XML document. Typical step kinds include:

- `plan` — an intended sequence;
- `premise` — a condition the plan depends on;
- `claim` — an assertion that can be checked;
- `tool_intent` — a proposed tool call and its reversibility.

This is not a raw-token cancellation protocol. The floor waits for a
checkable unit, records the unit, and then applies the monitor verdict.
A live `LlmMonitor` call is a blocking HTTP request for that unit.
Only askable kinds (`premise`, `claim`, `tool_intent`, and `answer_draft`) make that call, and exhausting `max_requests` without a committed answer raises `SessionError`, a legitimate result when the session does not finish.
Specialist generation does not continue in the background while the
supervisor answers. The live specialist Responses request streams in the
foreground (`background` is false). An interrupt closes that stream and
then POSTs cancel. Mock tests lock that request mode; a successful cancel
HTTP response is not proof the provider stopped generating.

## Monitor verdicts

The supervisor monitor returns a small verdict vocabulary:

- `Unknown` — insufficient evidence; do not interrupt by default, and do not
  commit a final answer without `Ok`;
- `Ok` — the current path can continue;
- `Patch` — interrupt **and correct**: supply missing or replacement facts,
  then continue;
- `False` — interrupt because the path is unsupported or unsafe (block a
  tool or answer; resume may still carry a directive).
  If that `False` has no rollback watermark and no ingested unit, the
  session holds: it does not commit and does not start a resume request.
  The trace records `answer.rejected`.

The neutral default matters. A missing or malformed supervisor response must
not become an aggressive interruption. The current parser maps malformed or
unknown supervisor states to `Unknown`.

## Interrupt, correction, and rollback

The floor is not a cancel-only switch. Two outcomes matter:

1. **Block** — do not execute the unsafe tool or commit the unsupported
   answer.
2. **Correct** — drop the rejected tail, attach a `Patch` (missing facts and
   a directive), and ask the specialist again from the last accepted `ThoughtUnit`.

An interrupt aborts the current request. Resume is a **new request** carrying a
watermarked prefix and, when available, a patch. That is context replay, not a
rewind of provider model state. The specialist must implement `apply_resume`;
a generate-only model cannot silently skip the envelope. The default resume
mode is `rollback`: continue the reasoning process mid-stream rather than
restarting the entire task from scratch.

The result exposes enough information for a host to inspect the outcome,
including committed output, interrupt identifiers, dropped units, request
count, and tool calls.

## Named handoffs

A monitor can end the current specialist while the verdict stays `Ok`.
The verdict names one receiver:

- `escalate_to` — another specialist should finish the task;
- `consult_to` — a checker should answer, and that answer comes back to the same specialist;
- `takeover_to` — an owner should receive the task.

`Unknown` does not open a route. A blank name does not open a route. When a verdict carries more than one name, the session uses escalation, then consultation, then takeover.

The current specialist stops. The uncommitted answer is not committed. The kept-step prefix leaves out dropped steps and that uncommitted answer. The host reads `escalate_to`, `consult_to`, or `takeover_to` on the session result and decides whether a later session starts.

`Escalation`, `Consult`, and `Takeover` compose the text the receiver reads. They do not call `run_session`. The same three objects share one package shape:

- the original task;
- the receiver's name (`role`);
- the supervisor's reason;
- the kept-step prefix;
- a `result {name}: {result}` line for each tool call that recorded a result;
- a closing line that names the tool calls which must not be repeated.

`from_result(task, result)` reads the matching floor event (`floor.escalate`, `floor.consult`, or `floor.takeover`). `from_note(task, note)` reads a note the host already has. `text()` returns the package.

```mermaid
flowchart TB
  session[Current run_session]
  monitor[Supervisor]
  session --> monitor
  monitor -->|escalate_to| next[Host opens the next specialist]
  monitor -->|consult_to| checker[Host runs the checker]
  checker --> patch[Patch returns to the same specialist]
  monitor -->|takeover_to editor| editor[Host opens the editor]
  monitor -->|takeover_to human| human[Host returns the package]
```

### Escalation

`result.escalate_to` names the next specialist. The first specialist does not resume. The host starts a new `run_session` for that specialist and passes `Escalation.from_result(task, result).text()` as the new request.

The graph, crew, or agent list does not choose the specialist. The host opens the next session only when the name is present.

See [`examples/supervisor_escalation.py`](../examples/supervisor_escalation.py) and [`cases/langgraph-offer/`](../cases/langgraph-offer/).

### Consultation

`result.consult_to` names the checker. The host runs that checker on `Consult.from_result(task, result).text()`. The checker's committed answer returns to the same specialist as a `Patch` on a new `run_session(..., resume_patch=...)`. The owner of the task stays where it was.

The same chat history, or the same assistant object, continues from the kept prefix plus that patch. The checker does not become the new owner.

See [`examples/supervisor_consult.py`](../examples/supervisor_consult.py) and [`cases/langchain-rule/`](../cases/langchain-rule/).

### Takeover

`result.takeover_to` names the owner.

`editor` is another specialist. The host may open a second `run_session` with `Takeover.from_result(task, result).text()`. The first specialist does not resume.

`human` is not a specialist. The host returns that same package text. No second specialist starts, and the monitor does not write the reply the person will see.

See [`examples/supervisor_takeover.py`](../examples/supervisor_takeover.py) and [`cases/autogen-support/`](../cases/autogen-support/).

## Tool safety

Tools are not executed merely because the model emitted a
`tool_intent`. The floor and host must permit the intent first.
`run_session(..., tool_policy=None)` is allow-if-Ok: after an `Ok` verdict the
supplied tool runs. That default is for demos and OSS examples, not production
authorization. Hosts must pass `tool_policy(name, args)` for consequential
tools. Returning `False` skips execute even when the model labeled the intent
reversible. Model `reversible` is intent only.

Three checks, in this order:

1. The monitor verdict on the `ThoughtUnit`.
2. The host `tool_policy(name, args)`. An `Ok` verdict and
   `reversible="true"` do not authorize a name the host refuses.
   [`examples/tool_policy_deny.py`](../examples/tool_policy_deny.py) shows
   that with no API key: `publish` is denied and `save_draft` still runs.
3. A person at the tool boundary, when the host adds that gate. It does not
   replace the monitor or the host policy.

The current examples exercise:

- an irreversible tool that must not run after a false premise;
- a sandbox writer that rejects paths outside its root;
- a downstream writer that is never started when an upstream specialist is
  interrupted.

The examples use dummy tools or sandbox files. They do not control a real
database, Git repository, email system, or deployment.

## Visible reasoning boundary

The protocol uses checkable task steps as an application communication
surface. It is not a mechanism for transporting hidden chain-of-thought.
Applications should emit only the structured information needed for checking,
coordination, and the final answer.
