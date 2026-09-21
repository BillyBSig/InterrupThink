# Limitations

[English](limitations.md) · [Bahasa Indonesia](id/limitations.md)

InterrupThink is an experimental library. The current evidence is useful for
checking the floor's contracts, but it is not sufficient for a production
deployment decision.

## Evaluation limitations

- Most checks use synthetic fixtures and deterministic `FakeLlm` responses.
- The allow path is a local control path, not a model-quality baseline.
- Live model smoke runs are nondeterministic and depend on provider,
  prompting, model version, network, and credentials.
- Results do not include confidence intervals, repeated random seeds, latency,
  throughput, or cost measurements.
- Optional framework tests depend on the versions installed in the local
  environment and may be skipped when a package is absent.
- No claim here compares InterrupThink with another orchestration system.

## Runtime limitations

- A resume request is new work with a watermark; it is not KV-cache rewind.
- Correction-and-continue is demonstrated on a synthetic fixture. It is not a
  claim that interruption improves model accuracy in general.
- The current rollback behavior does not provide durable distributed
  checkpointing or process recovery.
- A live `LlmMonitor` verdict is a blocking HTTP call per `ThoughtUnit`.
  Generation and supervision do not overlap.
- The live specialist request does not enable background continuation.
  `cancel_ok` records whether the cancel HTTP call succeeded, not whether
  generation stopped on the provider.
- `Unknown` is the default monitor state. It is conservative, but it can miss
  an issue when the monitor lacks evidence.
- Semantic step parsing depends on the specialist producing the expected
  structured document.
- A monitor verdict is not a proof of correctness.

## Side-effect limitations

- Examples use dummy tools, local files, and sandbox paths.
- No real Git repository, database, email provider, deployment system, or
  external vector database is modified by the documented cases.
- A path guard does not protect against a compromised process with access to
  the host.
- Tool authorization, credentials, retries, idempotency, and transactional
  behavior remain the host application's responsibility.
- Omitting `tool_policy` (`tool_policy=None`) is allow-if-Ok for demos and
  OSS examples. It is not production authorization. Consequential tools
  need an explicit host policy. Model-declared `reversible` is not host
  authorization.

## Scope limitations

The project does not currently claim:

- a user interface or production service;
- voice activity detection or audio interruption;
- symmetric specialist-to-specialist barge-in;
- a multi-agent mesh;
- hidden chain-of-thought transport;
- token-level orchestration;
- framework replacement;
- PyPI release readiness.

These limitations are part of the result, not footnotes to be ignored. New
claims require a separate evaluation with its own question, baseline, primary
metric, and reproduction path.
