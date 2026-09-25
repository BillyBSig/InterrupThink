# Dummy call sites — deterministic, no API key

Every file in this folder uses `FakeLlm` and `DummyTool` (or
`SandboxWriteTool` on a scratch fixture). They never call a live model. Run
them straight after `pip install -e .`, with no `.env` file and no
credentials.

The rest of [`examples/`](../) calls `LiveLlm` against a real provider and
needs a personal API key. This split is deliberate: a reader who only wants
to see the floor's contract (interrupt, correct, resume) should not need
credentials, and a reader wiring a real model should not have to guess which
files are safe to skip.

| File | Shows |
|------|-------|
| [`run_session_dummy.py`](run_session_dummy.py) | Minimal `run_session` wiring: block an unsafe `publish` on a wrong premise |
| [`host_loop_dummy.py`](host_loop_dummy.py) | Why the cut happens at the ThoughtUnit, not only at the host's tool-approval boundary |
| [`freeze_push_dummy.py`](freeze_push_dummy.py) | The same freeze-then-push story as a third, independent dummy app |
| [`staging_migrate.py`](staging_migrate.py) | A canned staging-migration call site, paired with `staging_case.py` |
| [`staging_case.py`](staging_case.py) | Shared scenario helper: `run_staging_case` (`FakeLlm`, used above) and `run_staging_live` (`LiveLlm`, used by [`../staging_migrate_live.py`](../staging_migrate_live.py)) |
| [`tool_policy_deny.py`](tool_policy_deny.py) | `run_session` + `tool_policy`: refuse `publish` after the monitor returns `Ok` |
| [`host_idempotent_tool.py`](host_idempotent_tool.py) | Same step key writes once; rollback keeps the store |
| [`supervisor_escalation.py`](supervisor_escalation.py) | `Escalation`: next specialist starts only after the supervisor names them |
| [`supervisor_handoff.py`](supervisor_handoff.py) | `Escalation`: named specialist receives the task, kept steps, and calls not to repeat |
| [`supervisor_consult.py`](supervisor_consult.py) | `Consult`: a checked consult returns as a patch to the same specialist |
| [`supervisor_consult_input.py`](supervisor_consult_input.py) | `Consult`: the checker reads the same package, then the same specialist continues |
| [`supervisor_takeover.py`](supervisor_takeover.py) | `Takeover`: a named owner continues from the kept steps; the first specialist does not |
| [`supervisor_takeover_input.py`](supervisor_takeover_input.py) | `Takeover`: editor and human receive the same package; the first specialist does not resume |

`staging_case.py` is the one file here that also backs a live call site.
Its `run_staging_live` function is imported by
[`examples/staging_migrate_live.py`](../staging_migrate_live.py) (a live
smoke script, not a dummy) via a local `sys.path` insert — the same pattern
`cases/*/run.py` files use for their own directory.

Full runnable stories with sandbox paths and tests live in
[`cases/`](../../cases/). The rest of the call sites in
[`examples/`](../) show **how to call** `interrupthink` against a real
model.
