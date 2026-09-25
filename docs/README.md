# InterrupThink Documentation

*Interruptible Reasoning at Thought Units (IRTU)*

[English](README.md) · [Bahasa Indonesia](id/README.md)

InterrupThink is an experimental open-source Python library for interrupting
**and correcting** reasoning at semantic `ThoughtUnit` boundaries instead of
raw token boundaries.

The library gives a host application a small 1:1 thinking floor:

1. A specialist produces checkable steps.
2. A monitor observes those steps.
3. An interrupt can **stop** an unsafe or unsupported path **and inject a
   correction** (`Patch`), then resume with a watermark.
4. An `Ok` verdict can also name a receiver: escalation to the next
   specialist, consultation back to the same specialist, or takeover by an
   editor or a human. `Escalation`, `Consult`, and `Takeover` compose that
   package. The host opens the next session.
5. The host commits only the approved, watermarked result.

A full restart is the fallback. The intended default is to continue the
reasoning process from the last accepted step.

This documentation is intentionally evidence-led. It describes what the
current implementation and tests demonstrate, what remains experimental, and
what has not been evaluated. It does not claim production readiness or model
quality.

## Quickstart

The package currently installs from the source repository. It is not published
to PyPI.

```bash
uv pip install -e .
python3 examples/dummy/run_session_dummy.py
```

The public import surface is deliberately small:

```python
from interrupthink import LlmMonitor, ThoughtUnit, run_session
```

Start with [Getting started](getting-started.md), then read
[Concepts](concepts.md) to understand interrupt, **correction**, and rollback.

## Documentation map

- [Getting started](getting-started.md) — install, run, and inspect a first session.
- [Concepts](concepts.md) — semantic units, verdicts, correction, rollback, named handoffs, and tool safety.
- [Integrations](integrations.md) — native hosts and optional framework examples.
- [Evaluation protocol](evaluation.md) — how claims are tested and compared.
- [Results](results.md) — the current public evidence summary (deterministic tests).
- [Live evaluation](live-evaluation.md) — opt-in checks against a real hosted model.
- [Limitations](limitations.md) — scope boundaries and open questions.
- [Reproducibility](reproducibility.md) — commands, environments, and reporting.
- [Publication policy](PUBLICATION_POLICY.md) — what belongs in this public directory.
- [Contributing](CONTRIBUTING.md) — how to improve the documentation.

## What the evidence supports

The current test suite supports contract-level claims about:

- blocking an irreversible tool before execution;
- preventing an invalid answer from reaching a downstream sink;
- **correcting** a wrong premise and continuing with rollback (not only
  cancelling the session);
- keeping framework integrations optional;
- preserving the same floor when a host uses LangGraph, LangChain,
  LlamaIndex, CrewAI, or AutoGen labels;
- mapping malformed supervisor verdicts to the neutral `Unknown` state;
- handing kept work to a named receiver through escalation, consultation,
  or takeover, without committing the unfinished answer.

These are small, deterministic or sandboxed checks. They are not a
production benchmark, a safety certification, or a comparison of language
models.

## Scope and non-goals

InterrupThink is not currently:

- a user interface;
- a production orchestration service;
- a multi-agent mesh with symmetric barge-in;
- a voice, VAD, or streaming-audio system;
- a hidden chain-of-thought transport;
- a database, email, Git, or deployment controller.

Optional framework packages are installed separately for their examples. They
are not core dependencies of the library.

## Source and license

The implementation lives in the source repository that contains this
directory. Start with the [source README](../README.md) for the codebase and
the [examples](../examples/).

Copyright 2026 BillyBSig. The source and this documentation are licensed
under the [Apache License, Version 2.0](../LICENSE). Redistribute only with
the license terms. Publishing to PyPI remains a separate decision.
