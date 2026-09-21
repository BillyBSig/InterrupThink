# Evaluation protocol

[English](evaluation.md) · [Bahasa Indonesia](id/evaluation.md)

## Purpose

The current evaluation asks two contract questions:

> Can a host **stop** an unsupported semantic step before its side effect is
> committed?
>
> After a cut, can the same host **correct** the reasoning process (patch +
> watermark) and **continue** with rollback, rather than only cancelling or
> restarting from scratch?

This is contract verification for a library floor. It is not a benchmark of
language-model quality, latency, throughput, or general agent performance.

## Comparison design

Every side-effect case has a control path:

- **interrupt path** — a false or unsupported premise is detected before the
  tool, answer sink, or downstream session;
- **correct-and-continue path** — after the cut, a patch is applied and the
  specialist resumes from the checkpoint (`rollback`);
- **allow path** — the same shape of task proceeds when no interrupt is
  triggered.

The allow path is the local serial/control comparison. Claims are limited to
the observed side effect and session behavior in the fixture.

## Evidence classes

### Deterministic contract tests

The primary evidence uses `FakeLlm`, scripted monitors, sandbox tools, and
small fixtures. These tests are repeatable and do not require an API key.

They verify:

- parsed semantic units and monitor verdicts;
- interrupt ordering;
- absence or presence of a sandbox side effect;
- rollback event fields;
- optional dependency behavior;
- local wheel installation.

### Live smoke paths

The command-line case runners can use `LiveOpenAILlm` and `LlmMonitor` with a
personal environment file. Each live monitor verdict waits for the provider
before the session continues. These runs demonstrate wiring against a live
model, but they are not deterministic and are not used to claim model accuracy.

No project API key is required or stored. Credentials must never be committed.

## Reproduction commands

From the source repository root:

```bash
uv venv
uv pip install -e ".[dev]"
python3 docs/check_publication.py
python3 -m pytest tests/test_public_api.py tests/test_library_packaging.py tests/test_wheel_install.py -x --tb=short -q
python3 -m pytest tests/test_sandbox_write.py tests/test_correct_resume.py tests/test_spike_paths.py -x --tb=short -q
python3 -m pytest tests/test_two_specialists.py tests/test_false_policy.py tests/test_deny_answer_pipeline.py -x --tb=short -q
python3 -m pytest tests/test_llm_monitor.py tests/test_run_session_contract.py -x --tb=short -q
```

Optional framework tests skip cleanly when their package is absent. When the
framework is installed in the environment, run the corresponding test file:

```bash
python3 -m pytest tests/test_langgraph_node.py tests/test_langgraph_apply.py tests/test_langgraph_correct.py -q
python3 -m pytest tests/test_langchain_extra.py tests/test_langchain_chat.py tests/test_langchain_correct.py -q
python3 -m pytest tests/test_llamaindex_extra.py -q
python3 -m pytest tests/test_crewai_extra.py tests/test_crewai_correct.py tests/test_autogen_extra.py tests/test_autogen_correct.py -q
```

The exact Python version, package state, and source revision must accompany
any externally reported result. See [Reproducibility](reproducibility.md).

## What counts as a pass

A scenario is reported as passing only when its primary contract is observed:

- the interrupt happens before the protected side effect;
- after a correction, resume continues from the watermark rather than only
  aborting the session;
- the allow/control path produces the expected bounded side effect;
- the session result records the expected interrupt or rollback data;
- optional host packages do not become core dependencies;
- the test can be mapped to a source test or a committed case.

If a dependency is unavailable, the result is `not evaluated` or `skipped`,
not a success inferred from source inspection.

## Reporting discipline

Public results distinguish:

- deterministic test evidence from live smoke evidence;
- a scenario contract from a production guarantee;
- a local control comparison from a baseline benchmark;
- a passed test from an untested framework or deployment mode.

Results do not include private prompts, raw model responses, environment
values, generated traces, or internal research identifiers.
