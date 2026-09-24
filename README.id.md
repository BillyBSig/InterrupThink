# InterrupThink

*Interruptible Reasoning at Thought Units* (IRTU)

[English](README.md) · [Bahasa Indonesia](README.id.md)

Pemeriksaan pada output akhir dapat menyembunyikan jawaban yang keliru, tetapi
tidak menunjukkan premise mana yang perlu diperbaiki sebelum premise itu
mengarahkan tool, handoff, atau turn chat berikutnya. InterrupThink
memungkinkan supervisor **menginterupsi** specialist pada batas `ThoughtUnit`
yang dapat diperiksa dan **mengoreksi** jalur penalarannya—bukan sekadar
membatalkan proses, dan bukan pula pada batas token mentah.

InterrupThink adalah library eksperimental, bukan produk atau layanan hosted.

[Mulai cepat](docs/id/getting-started.md) · [Contoh](examples/) · [Kasus](cases/) · [Konsep](docs/id/concepts.md) · [Berkontribusi](CONTRIBUTING.md) · [Lisensi](LICENSE)

## Mulai cepat

Memerlukan Python 3.11 atau lebih baru. Eksekusi live memanggil endpoint yang
kompatibel dengan OpenAI Responses API. Salin `.env.example` ke `.env`, lalu
isi model, base URL, dan key.

```bash
cp .env.example .env
uv pip install -e .
python3 cases/freeze-write/run.py
```

```python
from interrupthink import LiveLlm, LlmMonitor, run_session

result = run_session(
    llm=LiveLlm(user_prompt="Check the claim, then answer."),
    monitor=LlmMonitor(),
)
# result.committed_answer, interrupt_ids, dropped_ids, request_count, tool_calls
```

`LiveLlm` membaca `LLM_MODEL`, `LLM_BASE_URL`, dan `LLM_API_KEY` (atau
`OPENAI_API_KEY`). Base URL default-nya adalah `https://api.openai.com/v1`.
Arahkan `LLM_BASE_URL` ke endpoint lain yang menerima bentuk request yang
sama. `LlmMonitor` membaca variabel `SUPERVISOR_*`.

### Tanpa API key

Thinking floor yang sama juga menerima specialist scripted. Jalur ini tidak
memerlukan API key dan selalu menghasilkan output yang sama.

```bash
python3 examples/run_session_dummy.py
```

```python
from interrupthink import DummyTool, FakeLlm, ScriptedMonitor, run_session

tool = DummyTool()
llm = FakeLlm([wrong_xml, stopped_xml])
monitor = ScriptedMonitor(trigger_kind="premise", trigger_contains="already approved")
result = run_session(llm=llm, monitor=monitor, tool=tool)
```

Kebijakan host diperiksa secara terpisah.
[`examples/tool_policy_deny.py`](examples/tool_policy_deny.py) menolak
`publish` setelah monitor mengembalikan `Ok`.

Setelah interupsi, `FakeLlm` harus menyediakan dokumen XML kedua. `run_session`
tidak menambahkan prompt khusus aplikasi ke request.

Wheel lokal (masih **bukan** PyPI):

```bash
uv build --wheel
uv pip install --offline --no-index dist/interrupthink-0.0.1-py3-none-any.whl
```

## Mengapa ini diperlukan

Language model dapat menghasilkan jawaban yang terdengar meyakinkan, meskipun
jawaban itu bertumpu pada informasi yang usang atau belum lengkap. Risikonya
bertambah ketika jawaban bukan akhir dari pekerjaan. Dalam chat, klaim yang
salah dapat tersimpan di history dan memengaruhi turn berikutnya. Dalam
workflow, klaim itu dapat mengarah ke tindakan tool atau diteruskan ke
specialist lain.

Bayangkan assistant rilis membaca catatan lama yang menyebut sebuah rilis telah
disetujui. Assistant itu dapat menyiapkan publish, lalu menyatakan bahwa
publish aman dilakukan. Pemeriksaan pada output akhir masih dapat menolak
jawaban yang terlihat. Namun, pemeriksaan itu sendiri belum memberi aplikasi
checkpoint yang jelas untuk klaim persetujuan, tindakan yang direncanakan, dan
pekerjaan yang sebenarnya sudah benar. Pilihan yang biasa diambil adalah
membuang seluruh jawaban lalu mengulang dari awal.

InterrupThink menambahkan checkpoint tersebut sebelum aplikasi meng-commit
jawaban atau tindakan. Aplikasi mengeluarkan langkah tugas kecil yang
terstruktur; supervisor memeriksanya; lalu aplikasi dapat menghentikan jalur
yang tidak didukung atau memberikan fakta yang kurang dan melanjutkan dari
langkah terakhir yang diterima. Supervisor bukan penentu kebenaran mutlak:
ia bekerja berdasarkan bukti dan kebijakan yang diberikan aplikasi, sementara
`Unknown` tetap menjadi default ketika buktinya tidak memadai.

## Cara kerjanya

### Periksa keputusan sebelum di-commit

Aplikasi host tetap memiliki graph, role, atau tool-nya sendiri. `run_session`
menjadi batas checkpoint: specialist menghasilkan langkah `ThoughtUnit` yang
dapat diperiksa, supervisor memantaunya, dan tool atau jawaban hanya
di-commit jika diizinkan. Gate pada output akhir tetap berguna; floor ini
memberinya konteks yang lebih awal dan terstruktur.

Dengan demikian, tersedia dua respons. Floor dapat **memblokir** tindakan
tidak aman atau jawaban yang tidak didukung. Floor juga dapat **mengoreksi**
jalurnya: membuang bagian akhir yang ditolak, menambahkan `Patch`, lalu
melanjutkan dari langkah terakhir yang diterima tanpa memulai ulang seluruh
tugas. Pola ini penting ketika host dapat membawa klaim yang salah ke turn
chat berikutnya, panggilan tool, atau handoff bernama.

“Penalaran” di sini berarti langkah tugas terstruktur yang memang dipilih
aplikasi untuk dikeluarkan, misalnya plan, premise, claim, atau tool intent.
Ini bukan mekanisme untuk membaca atau mengirim hidden chain-of-thought.

Default setelah cut adalah **rollback**: sisipkan koreksi, buang bagian akhir
yang tidak valid, lalu lanjutkan dari langkah terakhir yang diterima. Restart
penuh adalah pilihan cadangan. Default monitor adalah `Unknown` (jangan
melakukan cut). Import package sebagai `interrupthink`.

```mermaid
flowchart TB
  host[Aplikasi host]
  session["run_session"]
  specialist[Specialist]
  units[Langkah ThoughtUnit]
  monitor[Supervisor monitor]
  commit[Commit tool atau jawaban]
  correct[Masukkan Patch]
  block[Blokir tindakan tidak aman]
  resume[Rollback dengan watermark]
  host --> session
  session --> specialist
  specialist --> units
  units --> monitor
  monitor -->|Ok| commit
  monitor -->|Unknown| hold[Tahan jawaban / lanjutkan langkah]
  monitor -->|Patch| correct
  monitor -->|False| block
  correct --> resume
  block --> resume
  resume --> specialist
  commit --> host
```

| Komponen | Peran |
|-------|------|
| `ThoughtUnit` | Satu langkah yang dapat diperiksa dalam dokumen specialist |
| `run_session` | Thinking floor: specialist bekerja, monitor mengamati, dan tool hanya berjalan jika diizinkan |
| `LlmMonitor` / `ScriptedMonitor` | Verdict blocking per `ThoughtUnit` sesuai kebutuhan; default `Unknown` |
| `Patch` / `False` | Interupsi: blokir jalur yang buruk atau masukkan koreksi |
| rollback | Lanjutkan di tengah aliran dari checkpoint—bukan restart dari awal |
| `Escalation` | Paket untuk specialist berikutnya. Specialist pertama tidak melanjutkan |
| `Consult` | Paket untuk checker. `Patch` kembali ke specialist yang sama |
| `Takeover` | Paket untuk editor atau manusia. Manusia tidak memulai specialist kedua |

Rakit floor sendiri. Jalur publik tidak mewajibkan helper produk siap pakai.

Verdict `Ok` juga dapat menyebut penerima. `Unknown` dan nama kosong tidak.
`Escalation`, `Consult`, dan `Takeover` menyusun paket tersebut. Ketiganya
tidak memanggil `run_session`. Host membuka sesi berikutnya hanya bila nama
penerima ada. Paket menyimpan tugas asli, penerima, alasan supervisor,
langkah-langkah yang dipertahankan, hasil tool yang tercatat, serta panggilan
yang tidak boleh diulang. Jawaban yang belum selesai tidak di-commit.

Rincian lebih lanjut: [`docs/id/concepts.md`](docs/id/concepts.md).

### Escalation

Specialist berikutnya menerima paket. Specialist pertama tidak melanjutkan.

```python
from interrupthink import Escalation, ScriptedMonitor, run_session

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
    # Pass package.text() into a new run_session for the policy specialist.
```

Lokasi pemanggilan:
[`examples/supervisor_escalation.py`](examples/supervisor_escalation.py).
Demo live:
[`examples/langgraph_offer_escalation.py`](examples/langgraph_offer_escalation.py).
Cookbook: [`cases/langgraph-offer/`](cases/langgraph-offer/).

### Consultation

Checker membaca paket. Jawaban checker kembali ke specialist yang sama sebagai
`Patch`.

```python
from interrupthink import Consult, Patch, ScriptedMonitor, run_session

result = run_session(
    llm=assistant,
    monitor=ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="ask the checker",
        consult_to="checker",
    ),
)
if result.consult_to:
    package = Consult.from_result(task, result)
    checker = run_session(llm=checker_llm, monitor=monitor)
    note = next(event.payload for event in result.events if event.type == "floor.consult")
    answer = checker.committed_answer or ""
    patch = Patch(
        from_agent="A",
        target_unit_id=str(note["unit_id"]),
        rollback_to=None,
        diagnosis="consult",
        missing=answer,
        directive=answer,
    )
    continued = run_session(llm=assistant, monitor=monitor, resume_patch=patch)
```

`checker_llm` seharusnya menerima `package.text()`. `assistant` adalah
specialist yang sama seperti sesi pertama.

Lokasi pemanggilan:
[`examples/supervisor_consult.py`](examples/supervisor_consult.py).
Demo live:
[`examples/langchain_rule_consult.py`](examples/langchain_rule_consult.py),
[`examples/llamaindex_page_consult.py`](examples/llamaindex_page_consult.py).
Cookbook: [`cases/langchain-rule/`](cases/langchain-rule/),
[`cases/llamaindex-page/`](cases/llamaindex-page/).

### Takeover

`editor` adalah specialist lain dan dapat menerima `run_session` baru.
`human` bukan: kembalikan paket dan jangan mulai specialist kedua.

```python
from interrupthink import ScriptedMonitor, Takeover, run_session

result = run_session(
    llm=support,
    monitor=ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="the supervisor should take this",
        takeover_to="human",
    ),
)
if result.takeover_to == "human":
    package = Takeover.from_result(task, result)
    # Return package.text() to the person. Do not open another run_session.
```

Lokasi pemanggilan:
[`examples/supervisor_takeover.py`](examples/supervisor_takeover.py).
Demo live:
[`examples/autogen_support_takeover.py`](examples/autogen_support_takeover.py).
Bentuk editor:
[`examples/database_takeover.py`](examples/database_takeover.py).
Cookbook: [`cases/autogen-support/`](cases/autogen-support/).

## Contoh

Lokasi pemanggilan singkat setelah `pip install -e .`. Cerita lengkap ada di
[`cases/`](cases/).

| File | Pemanggilan |
|------|--------|
| [`examples/run_session_dummy.py`](examples/run_session_dummy.py) | `run_session` |
| [`examples/staging_migrate.py`](examples/staging_migrate.py) | contoh staging-migrate siap pakai (helper lokal) |
| [`examples/freeze_push_dummy.py`](examples/freeze_push_dummy.py) | freeze + `push` dummy |
| [`examples/host_loop_dummy.py`](examples/host_loop_dummy.py) | host loop; HITL di batas tool |
| [`examples/tool_policy_deny.py`](examples/tool_policy_deny.py) | host menolak `publish` setelah monitor `Ok` |
| [`examples/supervisor_escalation.py`](examples/supervisor_escalation.py) | `Escalation`: specialist berikutnya menerima paket |
| [`examples/supervisor_consult.py`](examples/supervisor_consult.py) | `Consult`: patch kembali ke specialist yang sama |
| [`examples/supervisor_takeover.py`](examples/supervisor_takeover.py) | `Takeover`: editor atau manusia menerima paket |
| [`examples/langgraph_offer_escalation.py`](examples/langgraph_offer_escalation.py) | escalation LangGraph |
| [`examples/langchain_rule_consult.py`](examples/langchain_rule_consult.py) | consultation LangChain |
| [`examples/crewai_order_escalation.py`](examples/crewai_order_escalation.py) | escalation CrewAI |
| [`examples/autogen_support_takeover.py`](examples/autogen_support_takeover.py) | takeover AutoGen ke manusia |
| [`examples/llamaindex_page_consult.py`](examples/llamaindex_page_consult.py) | consultation LlamaIndex |

Demo framework menginstal framework tersebut di venv dengan `pip`, bukan
sebagai dependency inti. Daftar lengkapnya ada di
[`examples/README.md`](examples/README.md).

Runner case menggunakan `LiveLlm` dan `LlmMonitor` dengan `.env` pribadi.
Jangan commit key. File dummy `examples/*_dummy.py` tetap scripted.

## Integrasi

Framework host menyediakan struktur aplikasi, bukan loop penalaran semantik.
Setiap slot specialist tetap memanggil `run_session`. Integrasi opsional
diinstal terpisah dan dilewati dengan aman jika tidak tersedia.

| Host | Cookbook | Slot berpikir |
|------|----------|------------|
| Native | [`cases/two-specialists/`](cases/two-specialists/) | dua `run_session` |
| LangGraph | [`cases/langgraph-pipe/`](cases/langgraph-pipe/) | satu atau dua node, masing-masing `run_session` |
| LangChain | [`cases/langchain-specialist/`](cases/langchain-specialist/) | pertahankan thinking floor di sekitar framework |
| LlamaIndex | [`cases/llamaindex-retrieve/`](cases/llamaindex-retrieve/) | gunakan retriever untuk retrieval |
| CrewAI | [`cases/crewai-pipe/`](cases/crewai-pipe/) | pertahankan `run_session` di setiap role |
| AutoGen | [`cases/autogen-pipe/`](cases/autogen-pipe/) | pertahankan `run_session` di setiap agent |

Handoff bernama menggunakan floor yang sama. Framework mempertahankan node,
role, atau index-nya. Host menyusun paket dan membuka langkah berikutnya.

| Rute | Host | Cookbook | Demo |
|-------|------|----------|------|
| Escalation | LangGraph | [`cases/langgraph-offer/`](cases/langgraph-offer/) | [`examples/langgraph_offer_escalation.py`](examples/langgraph_offer_escalation.py) |
| Consultation | LangChain | [`cases/langchain-rule/`](cases/langchain-rule/) | [`examples/langchain_rule_consult.py`](examples/langchain_rule_consult.py) |
| Escalation | CrewAI | [`cases/crewai-order/`](cases/crewai-order/) | [`examples/crewai_order_escalation.py`](examples/crewai_order_escalation.py) |
| Takeover ke `human` | AutoGen | [`cases/autogen-support/`](cases/autogen-support/) | [`examples/autogen_support_takeover.py`](examples/autogen_support_takeover.py) |
| Consultation | LlamaIndex | [`cases/llamaindex-page/`](cases/llamaindex-page/) | [`examples/llamaindex_page_consult.py`](examples/llamaindex_page_consult.py) |

## Pengembangan

Lihat [`CONTRIBUTING.md`](CONTRIBUTING.md). Bukti, keterbatasan, dan cara
memperluas dokumen publik: [`docs/`](docs/).

```bash
uv pip install -e ".[dev]"
python3 -m pytest tests/test_public_api.py tests/test_library_packaging.py -x --tb=short -q
```

Library ini eksperimental. Ini bukan produk atau mesh multi-agent. Klaim publik
terbatas pada pemeriksaan dalam [`docs/results.md`](docs/results.md).

## Lisensi

Hak cipta 2026 BillyBSig. Dilisensikan di bawah
[Apache License, Version 2.0](LICENSE).
