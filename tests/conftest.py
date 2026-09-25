"""Keep provider credentials from leaking between tests.

Importing CrewAI calls ``load_dotenv()`` as soon as the package loads, which
copies this repository's ``.env`` into ``os.environ``. A later test that
expects those variables to be absent would then see the real key. Restoring
the process environment after every test closes that leak without uninstalling
the optional frameworks.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def restore_process_environ():
    """Snapshot ``os.environ`` and put it back after the test."""
    saved = os.environ.copy()
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)
