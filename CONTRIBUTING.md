# Contributing

This repository ships the **InterrupThink** library.

## Setup

Python 3.11+. Editable install from the repo root (not PyPI):

```bash
uv pip install -e ".[dev]"
```

Public import:

```python
from interrupthink import run_session, ThoughtUnit, LlmMonitor
```

The public import is `interrupthink`; there is no compatibility package with a
different name. Keep the library source and examples free of project-owned
credentials. Release and packaging decisions are documented separately from
the user-facing examples.

Dummy examples (no `.env`):

```bash
python3 examples/dummy/run_session_dummy.py
python3 examples/dummy/freeze_push_dummy.py
python3 examples/dummy/staging_migrate.py
```

Live cookbooks under `cases/` need a personal `.env`. Do not commit it or copy
its contents into an issue, example, or documentation page.

## Tests

Targeted checks while iterating:

```bash
python3 -m pytest tests/test_public_api.py tests/test_library_packaging.py -x --tb=short -q
```

Run the full suite before a commit or pull request. Framework extras
(`langgraph`, `langchain`, …) are optional virtual-environment installs.

## Documentation

Public docs live in [`docs/`](docs/). How to add a page: [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md). Evidence and limitations: [`docs/evaluation.md`](docs/evaluation.md), [`docs/results.md`](docs/results.md), [`docs/limitations.md`](docs/limitations.md).

## License

Contributions are accepted under the [Apache License, Version 2.0](LICENSE).
