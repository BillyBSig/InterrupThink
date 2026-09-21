# Mulai menggunakan InterrupThink

[English](../getting-started.md) · [Bahasa Indonesia](getting-started.md)

## Persyaratan

- Python 3.11 atau lebih baru;
- `uv` atau alat lain untuk membuat virtual environment;
- contoh deterministik tidak membutuhkan API key.

## Instalasi

Dari root repository:

```bash
uv pip install -e ".[dev]"
```

Package inti tidak memiliki dependency runtime khusus framework. Framework
opsional diinstal terpisah saat menjalankan contoh terkait.

## Jalankan contoh deterministik

```bash
python3 examples/run_session_dummy.py
```

Contoh ini menggunakan `FakeLlm`, `ScriptedMonitor`, dan `DummyTool`. Dengan
interupsi, pemanggilan publish yang irreversible tidak dijalankan. Pada jalur
tanpa interupsi, dummy tool dapat dipanggil.

Koreksi dilakukan melalui request kedua setelah interupsi: specialist
melanjutkan dari watermark dengan premise yang sudah dikoreksi, bukan
mengulang seluruh tugas.
Lihat [`cases/correct-resume/`](../../cases/correct-resume/).

## Jalankan sebuah sesi

```python
from interrupthink import DummyTool, FakeLlm, ScriptedMonitor, run_session

result = run_session(
    llm=FakeLlm([first_xml, second_xml]),
    monitor=ScriptedMonitor(trigger_kind="claim"),
    tool=DummyTool(),
)
```

Host dapat membaca `committed_answer`, `interrupt_ids`, `dropped_ids`,
`request_count`, dan `tool_calls` dari hasil sesi.

## Jalankan case live

Case live memerlukan `.env` pribadi:

```bash
python3 cases/correct-resume/run.py
```

Contoh live menggunakan `LiveOpenAILlm` dan `LlmMonitor`. Kredensial tidak
boleh disimpan di repository.
