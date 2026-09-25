# Mulai menggunakan InterrupThink

[English](../getting-started.md) · [Bahasa Indonesia](getting-started.md)

## Persyaratan

- Python 3.11 atau lebih baru;
- `uv` atau tool lain untuk membuat virtual environment;
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
python3 examples/dummy/run_session_dummy.py
```

Contoh ini menggunakan `FakeLlm`, `ScriptedMonitor`, dan `DummyTool`. Saat
terjadi interupsi, tool call `publish` yang tidak dapat dibatalkan tidak
dieksekusi; tanpa interupsi, control flow mencapai dummy tool.

Itu baru setengah dari floor. **Koreksi** adalah request kedua setelah cut:
specialist melanjutkan dari watermark dengan premise yang sudah di-patch,
bukan me-restart seluruh task. Lihat
[`cases/correct-resume/`](../../cases/correct-resume/) dan
`python3 cases/correct-resume/run.py`.

Tool menyimpan tool call di memori; tool tidak memublikasikan apa pun.

## Menyusun sesi

Thinking floor publik disusun dari implementasi LLM, monitor, dan tool
opsional:

```python
from interrupthink import DummyTool, FakeLlm, ScriptedMonitor, run_session

wrong = """
plan: publish the changelog
premise: the changelog is already approved
tool_intent: {"name":"publish","args":{"doc":"changelog"}}
answer: Published the changelog.
"""

stopped = """
claim: the changelog is not approved
answer: Did not publish.
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
`FakeLlm`, dokumen itu harus tersedia; jika tidak, sesi menghasilkan
`SessionError`. Ini disengaja: request yang diinterupsi dibatalkan lalu
dilanjutkan dengan request baru, bukan diam-diam meneruskan request lama.
`Patch` dapat membawa fakta pengganti pada request berikutnya agar specialist
melanjutkan reasoning, bukan hanya berhenti. Lihat
[Konsep](concepts.md) dan
[`cases/correct-resume/`](../../cases/correct-resume/).

## Serahkan task kepada penerima bernama

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

Kedua failure ini memang bagian dari kontrak. Perbaiki daftar dokumen skrip
atau output model; jangan melonggarkan parser.

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

`SessionError: llm has no further output for this request; after an interrupt, FakeLlm needs a second document`

Prosa biasa tanpa label bukan error; itu menjadi satu langkah `claim`:

```python
from interrupthink import parse_steps

doc = parse_steps("The changelog is already approved. Publish it.")
# doc.units[0].kind == "claim"
```

Badan langkah tanpa label tetap harus tidak kosong. Output kosong yang gagal:

```python
parse_steps("")
```

`ParseError: empty llm output`

## Panduan rujukan

| Jika Anda melihat ini | Buka ini lebih dulu |
|---|---|
| Tool berjalan sebelum premise diterima | [`examples/dummy/run_session_dummy.py`](../../examples/dummy/run_session_dummy.py) |
| Premise salah dan task tidak boleh di-restart dari kosong | [`cases/correct-resume/`](../../cases/correct-resume/) |
| Penulisan file harus tetap di dalam sandbox | [`cases/freeze-write/`](../../cases/freeze-write/) |
| Chunk atau catatan retrieval yang kedaluwarsa | [`cases/stale-retrieve/`](../../cases/stale-retrieve/) |
| Jawaban mengutip kebijakan yang tidak ada dalam source | [`cases/false-policy/`](../../cases/false-policy/) |
| Read diizinkan, delete tidak | [`cases/op-class/`](../../cases/op-class/) |
| Specialist kedua tidak boleh dimulai | [`cases/two-specialists/`](../../cases/two-specialists/) |
| Specialist berikutnya harus menerima work yang dipertahankan | [`examples/dummy/supervisor_escalation.py`](../../examples/dummy/supervisor_escalation.py), [`cases/langgraph-offer/`](../../cases/langgraph-offer/) |
| Specialist yang sama harus melanjutkan setelah checker | [`examples/dummy/supervisor_consult.py`](../../examples/dummy/supervisor_consult.py), [`cases/langchain-rule/`](../../cases/langchain-rule/) |
| Manusia harus menerima paket tanpa agent kedua | [`examples/dummy/supervisor_takeover.py`](../../examples/dummy/supervisor_takeover.py), [`cases/autogen-support/`](../../cases/autogen-support/) |
| `publish` tetap diminta setelah monitor `Ok` | [`examples/dummy/tool_policy_deny.py`](../../examples/dummy/tool_policy_deny.py) |
| Langkah tool berulang tidak boleh menulis lagi | [`examples/dummy/host_idempotent_tool.py`](../../examples/dummy/host_idempotent_tool.py) |
| Graph atau role yang sudah ada | [Integrasi](integrations.md) |

Case command-line yang memanggil `LiveLlm` membutuhkan environment file
pribadi. Dokumen scripted di atas adalah bentuk tanpa API key.

## Build wheel lokal

Path wheel lokal berguna untuk memeriksa instalasi dari working directory yang
bersih:

```bash
uv build --wheel
uv pip install --offline --no-index dist/interrupthink-0.0.1-py3-none-any.whl
```

Ini adalah local packaging check, bukan rilis ke PyPI.

## Jalankan sebuah case

Direktori [`../cases/`](../../cases/) berisi contoh host dalam sandbox. Test
deterministik menginjeksikan test double; case command-line dapat menggunakan
`LiveLlm` dengan environment file pribadi.

Contohnya:

```bash
python3 cases/freeze-write/run.py
python3 cases/two-specialists/run.py
```

Jangan commit kredensial atau file yang dihasilkan dari `tmp/` dan `runs/`.
