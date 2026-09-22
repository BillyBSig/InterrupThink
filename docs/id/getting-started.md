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

Contoh ini menggunakan `FakeLlm`, `ScriptedMonitor`, dan `DummyTool`. Saat
terjadi interupsi, pemanggilan tool `publish` yang tidak dapat dibatalkan tidak
dijalankan. Tanpa interupsi, dummy tool dapat dipanggil.

Koreksi dilakukan melalui request kedua setelah interupsi: specialist
melanjutkan dari watermark setelah premise dikoreksi, bukan mengulang seluruh
tugas.
Lihat [`cases/correct-resume/`](../../cases/correct-resume/).

## Menjalankan sesi

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

## Gagal yang diharapkan

Kedua kegagalan ini memang bagian dari kontrak. Perbaiki daftar dokumen skrip
atau keluaran model; jangan melonggarkan parser.

Jika `FakeLlm` hanya memiliki dokumen pertama, interupsi berikutnya akan
membutuhkan dokumen kedua:

```python
from interrupthink import FakeLlm, ScriptedMonitor, SessionError, run_session

try:
    run_session(
        llm=FakeLlm([first_xml]),
        monitor=ScriptedMonitor(trigger_kind="premise", trigger_contains="already approved"),
    )
except SessionError as exc:
    print(exc)
```

`SessionError: llm has no further output for this request; after an interrupt, FakeLlm needs a second XML document`

Teks yang tidak memuat `<step>` akan gagal di parser:

```python
from interrupthink import ParseError, parse_steps

parse_steps("The changelog is already approved. Publish it.")
```

`ParseError: no <step> element in llm output`

Jika teks prosa yang sama dikirim lewat `run_session`, yang muncul adalah
`ValueError: llm produced no complete <step>`. Assembler tidak pernah
menyerahkan satu langkah pun ke parser.

## Jika menemukan gejala berikut

| Gejala | Buka ini dulu |
|---|---|
| Tool jalan sebelum premis diterima | [`examples/run_session_dummy.py`](../../examples/run_session_dummy.py) |
| Premis salah, tugas jangan diulang dari kosong | [`cases/correct-resume/`](../../cases/correct-resume/) |
| Tulis file hanya di dalam sandbox | [`cases/freeze-write/`](../../cases/freeze-write/) |
| Chunk atau catatan yang sudah usang | [`cases/stale-retrieve/`](../../cases/stale-retrieve/) |
| Jawaban memakai kebijakan yang tidak ada di sumber | [`cases/false-policy/`](../../cases/false-policy/) |
| Baca boleh, hapus tidak | [`cases/op-class/`](../../cases/op-class/) |
| Spesialis kedua tidak boleh mulai | [`cases/two-specialists/`](../../cases/two-specialists/) |
| `publish` tetap diminta setelah monitor `Ok` | [`examples/tool_policy_deny.py`](../../examples/tool_policy_deny.py) |
| Langkah tool yang sama tidak boleh menulis lagi | [`examples/host_idempotent_tool.py`](../../examples/host_idempotent_tool.py) |
| Graf atau peran yang sudah ada | [Integrasi](integrations.md) |

Case CLI yang menggunakan `LiveLlm` memerlukan file lingkungan pribadi.
Contoh skrip di atas menunjukkan bentuk yang tidak membutuhkan kunci.

Case live memerlukan `.env` pribadi:

```bash
python3 cases/correct-resume/run.py
```

Contoh live menggunakan `LiveLlm` dan `LlmMonitor`. Kredensial tidak
boleh disimpan di repository.
