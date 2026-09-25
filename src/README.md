# Runtime support

This directory contains the parsing, runtime, monitoring, and provider
components used by the library and its examples.

```text
src/interrupthink/
  parse/       ThoughtUnit steps
  runtime/     floor, watermark, resume prefix, JSONL, session
  monitor/     ScriptedMonitor and LlmMonitor
  providers/   FakeLlm + LiveLlm (SSE abort)
  cli/         local command-line helpers
```

Import the library as `interrupthink`. The modules under `src/interrupthink/`
are the implementation behind `run_session`, structured steps, monitors, and
live or deterministic model providers.

The command-line helpers are useful for local experiments and examples; they
are not a separate product interface.
