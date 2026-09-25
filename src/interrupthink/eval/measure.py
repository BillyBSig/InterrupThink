"""Small live-monitor measurement harness. Does not lock G4.

Primary metric is locked in PROTOCOL before any trial numbers are interpreted.
Tests use mocked HTTP. A real-provider run is opt-in and is not public results.
``family_live`` names the intended family. ``executed_live`` is only True when
a real-provider run is recorded; mock summaries stay False.
"""

from __future__ import annotations

import time
import urllib.error
from dataclasses import asdict, dataclass
from typing import Any, Callable

# Locked 2026-09-21 before mock numbers. Do not change after results.
PROTOCOL = {
    "family": "live_monitor_smoke",
    "n_max": 3,
    "conditions": ("ok", "timeout", "cancel"),
    "primary_metric": "trace_complete",
    "family_live": True,
    "locks_g4": False,
    "public_results": False,
}

CONDITIONS = PROTOCOL["conditions"]
REQUIRED = ("model", "provider", "latency_ms", "timeout", "cancel_ok", "failure_category")


@dataclass
class MeasureRow:
    condition: str
    model: str
    provider: str
    latency_ms: float
    timeout: bool
    cancel_ok: bool | None
    failure_category: str | None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


def trace_complete(row: MeasureRow) -> bool:
    for key in REQUIRED:
        if not hasattr(row, key):
            return False
    if not row.model or not row.provider:
        return False
    if row.latency_ms < 0:
        return False
    return True


def measure_ok(
    *,
    model: str = "mock-supervisor",
    provider: str = "example.test",
    complete: Callable[..., str] | None = None,
) -> MeasureRow:
    fn = complete or (lambda **_: '{"status":"Ok"}')
    t0 = time.perf_counter()
    failure: str | None = None
    timeout = False
    usage: dict[str, Any] = {}
    try:
        raw = fn(model=model)
        if isinstance(raw, tuple):
            _, usage = raw
        else:
            usage = {}
    except TimeoutError:
        timeout = True
        failure = "timeout"
    latency_ms = (time.perf_counter() - t0) * 1000
    return MeasureRow(
        condition="ok",
        model=model,
        provider=provider,
        latency_ms=latency_ms,
        timeout=timeout,
        cancel_ok=None,
        failure_category=failure,
        input_tokens=_token(usage, "input_tokens"),
        output_tokens=_token(usage, "output_tokens"),
        cost_usd=None,
    )


def measure_timeout(
    *,
    model: str = "mock-supervisor",
    provider: str = "example.test",
    complete: Callable[..., str] | None = None,
) -> MeasureRow:
    def _boom(**_kwargs: Any) -> str:
        raise TimeoutError("timed out")

    fn = complete or _boom
    t0 = time.perf_counter()
    timeout = False
    failure: str | None = None
    try:
        fn(model=model)
    except TimeoutError:
        timeout = True
        failure = "timeout"
    except urllib.error.URLError as exc:
        timeout = True
        failure = "timeout"
        _ = exc
    latency_ms = (time.perf_counter() - t0) * 1000
    return MeasureRow(
        condition="timeout",
        model=model,
        provider=provider,
        latency_ms=latency_ms,
        timeout=timeout,
        cancel_ok=None,
        failure_category=failure,
        cost_usd=None,
    )


def measure_cancel(
    *,
    model: str = "mock-specialist",
    provider: str = "example.test",
    abort: Callable[[], bool] | None = None,
) -> MeasureRow:
    def _ok() -> bool:
        return True

    fn = abort or _ok
    t0 = time.perf_counter()
    failure: str | None = None
    cancel_ok = False
    try:
        cancel_ok = bool(fn())
    except (OSError, urllib.error.URLError, urllib.error.HTTPError):
        failure = "cancel_io"
        cancel_ok = False
    latency_ms = (time.perf_counter() - t0) * 1000
    return MeasureRow(
        condition="cancel",
        model=model,
        provider=provider,
        latency_ms=latency_ms,
        timeout=False,
        cancel_ok=cancel_ok,
        failure_category=failure,
        cost_usd=None,
    )


def run_family(
    *,
    complete_ok: Callable[..., str] | None = None,
    complete_timeout: Callable[..., str] | None = None,
    abort: Callable[[], bool] | None = None,
) -> list[MeasureRow]:
    return [
        measure_ok(complete=complete_ok),
        measure_timeout(complete=complete_timeout),
        measure_cancel(abort=abort),
    ]


def summarize(rows: list[MeasureRow], *, executed_live: bool = False) -> dict[str, Any]:
    n = len(rows)
    complete = sum(1 for row in rows if trace_complete(row))
    by = {row.condition: asdict(row) for row in rows}
    return {
        "family": PROTOCOL["family"],
        "n": n,
        "n_max": PROTOCOL["n_max"],
        "primary_metric": PROTOCOL["primary_metric"],
        "trace_complete": (complete / n) if n else 0.0,
        "by_condition": by,
        "protocol_ok": n == PROTOCOL["n_max"] and complete == n,
        "locks_g4": PROTOCOL["locks_g4"],
        "public_results": PROTOCOL["public_results"],
        "family_live": PROTOCOL["family_live"],
        "executed_live": executed_live,
    }


def _token(usage: dict[str, Any], key: str) -> int | None:
    value = usage.get(key) if isinstance(usage, dict) else None
    if value is None:
        return None
    return int(value)
