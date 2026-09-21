# Runtime support

This directory contains the parsing, runtime, monitoring, and provider
components used by the library and its examples.

```text
src/
  parse/       <step> / ThoughtUnit
  runtime/     floor, watermark, resume prefix, JSONL, session tiga jalur
  monitor/     ScriptedMonitor and LlmMonitor
  providers/   FakeLlm + LiveOpenAILlm (SSE abort)
  cli/         local command-line helpers
```

The public entry point is the `interrupthink` package. The modules here are
implementation details that support `run_session`, structured steps, monitors,
and live or deterministic model providers.

The command-line helpers are useful for local experiments and examples; they
are not a separate product interface.
