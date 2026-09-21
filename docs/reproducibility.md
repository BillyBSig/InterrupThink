# Reproducibility

[English](reproducibility.md) · [Bahasa Indonesia](id/reproducibility.md)

The public results are tied to source code, tests, environment assumptions,
and a declared evidence class. Re-running only a prose claim is not enough.

## Environment

- Python: 3.11 or newer
- Core dependencies: the committed source environment
- Optional frameworks: installed separately in the test environment
- Deterministic tests: no API key required
- Live smoke paths: personal provider credentials only; never project
  credentials

Create an isolated environment and install the core package:

```bash
uv venv
uv pip install -e ".[dev]"
```

The optional host frameworks are not part of the core dependency set. Install
only the package needed by the case being reproduced:

```bash
uv pip install langgraph
uv pip install langchain
uv pip install llama-index llama-index-llms-openai
uv pip install crewai
uv pip install autogen
```

## Deterministic checks

Run the core contract checks:

```bash
python3 docs/check_publication.py
python3 -m pytest tests/test_public_api.py tests/test_library_packaging.py tests/test_wheel_install.py -x --tb=short -q
python3 -m pytest tests/test_sandbox_write.py tests/test_correct_resume.py tests/test_spike_paths.py -x --tb=short -q
python3 -m pytest tests/test_two_specialists.py tests/test_false_policy.py tests/test_deny_answer_pipeline.py -x --tb=short -q
python3 -m pytest tests/test_llm_monitor.py tests/test_run_session_contract.py -x --tb=short -q
```

Run optional host checks after installing their packages:

```bash
python3 -m pytest tests/test_langgraph_node.py tests/test_langgraph_apply.py tests/test_langgraph_correct.py -q
python3 -m pytest tests/test_langchain_extra.py tests/test_langchain_chat.py tests/test_langchain_correct.py -q
python3 -m pytest tests/test_llamaindex_extra.py -q
python3 -m pytest tests/test_crewai_extra.py tests/test_crewai_correct.py tests/test_autogen_extra.py tests/test_autogen_correct.py -q
```

The complete suite is:

```bash
python3 -m pytest -q
```

## Evidence record

When reporting a reproduced result, include:

1. source revision or commit;
2. operating system;
3. Python version;
4. package installation commands;
5. optional framework versions;
6. exact test or case command;
7. exit status and observed artifact;
8. whether the result is deterministic or live-model evidence.

Do not include API keys, private prompts, raw model traces, or personal
environment values in a report.

## Differences are useful evidence

If a reproduction differs, preserve the failure and report the smallest
useful artifact: command, environment, test name, exception, and whether the
optional dependency was installed. Do not silently edit the expected result
to make a run pass.
