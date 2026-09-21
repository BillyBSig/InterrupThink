# Contributing to the documentation

[English](CONTRIBUTING.md) · [Bahasa Indonesia](id/CONTRIBUTING.md)

The documentation is maintained next to the source repository, but it has a
separate audience and publication boundary.

## Before editing

Read:

- [`README.md`](README.md) for the public scope;
- [`PUBLICATION_POLICY.md`](PUBLICATION_POLICY.md) for inclusion rules;
- [`evaluation.md`](evaluation.md) before adding a test claim.

Do not use internal planning documents as public copy. Use source tests and
sanitized results as evidence.

## Evidence-first changes

For a new claim, include:

1. the user-facing behavior;
2. the test or reproducible command;
3. the observed result;
4. the limitation and scope;
5. the distinction between deterministic and live-model evidence.

If evidence is unavailable, write `not evaluated` rather than guessing.

## Local checks

From the source repository root:

```bash
python3 -m pytest tests/test_public_api.py tests/test_library_packaging.py -x --tb=short -q
python3 -m pytest -q
python3 docs/check_publication.py
```

The optional framework tests may skip when their package is not installed.
That skip must not be described as a passing framework result.

## Style

- Use plain, direct English.
- Put the user action before implementation detail.
- Prefer short sections and runnable commands.
- Explain terms at first use.
- State what the evidence does not show.
- Avoid internal task numbers and project-status language.

## Pull requests

A documentation change should explain:

- which public audience it serves;
- which source code or tests support it;
- what was intentionally excluded;
- which local checks were run.

Do not include credentials, raw traces, private prompts, or generated case
artifacts in a pull request.

Documentation contributions follow the [Apache License, Version 2.0](../LICENSE).
