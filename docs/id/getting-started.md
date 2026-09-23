# Mulai menggunakan InterrupThink

[English](../getting-started.md) · [Bahasa Indonesia](getting-started.md)

## Persyaratan

- Python 3.11 atau lebih baru;
- `uv` atau alat lain untuk membuat virtual environment;
- contoh deterministik tidak membutuhkan API key.

Source repository saat ini menjadi sumber instalasi. Package belum
dipublikasikan ke PyPI.

## Instal library

Dari root source repository:

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
dieksekusi; tanpa interupsi, alur kontrol mencapai dummy tool.

Itu baru setengah dari floor. **Koreksi** adalah request kedua setelah cut:
specialist melanjutkan dari watermark dengan premise yang sudah di-patch,
bukan memulai ulang seluruh tugas. Lihat
[`cases/correct-resume/`](../../cases/correct-resume/) dan
`python3 cases/correct-resume/run.py`.

Tool mencatat pemanggilan di memori; tool tidak memublikasikan apa pun.

## Menyusun sesi

Thinking floor publik disusun dari implementasi LLM, monitor, dan tool
opsional:

```python
from interrupthink import DummyTool, FakeLlm, ScriptedMonitor, run_session

wrong = """
<step kind="plan">publish the changelog</step>
<step kind="premise">the changelog is already approved</step>
<step kind="tool_intent" reversible="false">
{"name":"publish","args":{"doc":"changelog"}}
</step>
<answer>Published the changelog.</answer>
"""

stopped = """
<step kind="claim">the changelog is not approved</step>
<answer>Did not publish.</answer>
"""

tool = DummyTool()
result = run_session(
    llm=FakeLlm([wrong, stopped]),
    monitor=ScriptedMonitor(
        trigger_kind="premise",
        trigger_contains="already approved",
    ),
    tool=tool,
)

assert result.interrupt_ids
assert tool.calls == []
```

`run_session` meminta dokumen kedua dari LLM setelah interupsi. Dengan
`FakeLlm`, dokumen itu harus tersedia; jika tidak, sesi menimbulkan
`SessionError`. Ini disengaja: request yang diinterupsi dibatalkan dan
dilanjutkan dengan request baru, bukan diam-diam meneruskan request lama.
`Patch` dapat membawa fakta pengganti pada request berikutnya agar specialist
melanjutkan proses penalaran, bukan hanya berhenti. Lihat
[Konsep](concepts.md) dan
[`cases/correct-resume/`](../../cases/correct-resume/).

## Serahkan tugas kepada penerima bernama

Hasil sesi yang sama dapat menyebut penerima tanpa melakukan commit pada
jawaban specialist yang belum selesai. Import `Escalation`, `Consult`, atau
`Takeover`, lalu susun paket dari hasil tersebut. Object itu tidak memulai sesi
berikutnya. Host yang melakukannya, dan hanya ketika nama penerima ada.

```python
from interrupthink import Escalation, ScriptedMonitor, run_session

# dealer is the first specialist. task is the original task string.
result = run_session(
    llm=dealer,
    monitor=ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="ask policy",
        escalate_to="policy",
    ),
)
if result.escalate_to:
    package = Escalation.from_result(task, result)
    # Give package.text() to the policy specialist as a new request.
```

Consultation menggunakan `Consult`, kemudian `Patch` kembali ke specialist yang
sama. Takeover menggunakan `Takeover`. Untuk `takeover_to="human"`, kembalikan
`package.text()` dan jangan mulai specialist kedua. Bentuk lengkapnya ada di
[Konsep](concepts.md#named-handoffs).

## Gagal yang diharapkan

Kedua kegagalan ini memang bagian dari kontrak. Perbaiki daftar dokumen skrip
atau keluaran model; jangan melonggarkan parser.

`FakeLlm` yang hanya memiliki dokumen pertama setelah interupsi:

```python
from interrupthink import FakeLlm, ScriptedMonitor, SessionError, run_session

try:
    run_session(
        llm=FakeLlm([wrong]),
        monitor=ScriptedMonitor(
            trigger_kind="premise",
            trigger_contains="already approved",
        ),
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

## Panduan rujukan

| Jika Anda melihat ini | Buka ini lebih dulu |
|---|---|
| Tool berjalan sebelum premise diterima | [`examples/run_session_dummy.py`](../../examples/run_session_dummy.py) |
| Premise salah dan tugas tidak boleh restart dari kosong | [`cases/correct-resume/`](../../cases/correct-resume/) |
| Penulisan file harus tetap di dalam sandbox | [`cases/freeze-write/`](../../cases/freeze-write/) |
| Chunk atau catatan retrieval yang kedaluwarsa | [`cases/stale-retrieve/`](../../cases/stale-retrieve/) |
| Jawaban mengutip kebijakan yang tidak ada dalam source | [`cases/false-policy/`](../../cases/false-policy/) |
| Read diizinkan, delete tidak | [`cases/op-class/`](../../cases/op-class/) |
| Specialist kedua tidak boleh dimulai | [`cases/two-specialists/`](../../cases/two-specialists/) |
| Specialist berikutnya harus menerima pekerjaan yang dipertahankan | [`examples/supervisor_escalation.py`](../../examples/supervisor_escalation.py), [`cases/langgraph-offer/`](../../cases/langgraph-offer/) |
| Specialist yang sama harus melanjutkan setelah checker | [`examples/supervisor_consult.py`](../../examples/supervisor_consult.py), [`cases/langchain-rule/`](../../cases/langchain-rule/) |
| Manusia harus menerima paket tanpa agent kedua | [`examples/supervisor_takeover.py`](../../examples/supervisor_takeover.py), [`cases/autogen-support/`](../../cases/autogen-support/) |
| `publish` tetap diminta setelah monitor `Ok` | [`examples/tool_policy_deny.py`](../../examples/tool_policy_deny.py) |
| Langkah tool berulang tidak boleh menulis lagi | [`examples/host_idempotent_tool.py`](../../examples/host_idempotent_tool.py) |
| Graph atau role yang sudah ada | [Integrasi](integrations.md) |

Case command-line yang memanggil `LiveLlm` membutuhkan file environment
pribadi. Dokumen scripted di atas adalah bentuk tanpa key.

## Build wheel lokal

Path wheel lokal berguna untuk memeriksa instalasi dari working directory yang
bersih:

```bash
uv build --wheel
uv pip install --offline --no-index dist/interrupthink-0.0.1-py3-none-any.whl
```

Ini adalah pemeriksaan packaging lokal, bukan rilis ke PyPI.

## Jalankan sebuah case

Direktori [`../cases/`](../../cases/) berisi contoh host dalam sandbox. Test
deterministik menginjeksikan double; case command-line dapat menggunakan
`LiveLlm` dengan file environment pribadi.

Contohnya:

```bash
python3 cases/freeze-write/run.py
python3 cases/two-specialists/run.py
```

Jangan commit kredensial atau file yang dihasilkan dari `tmp/` dan `runs/`.
