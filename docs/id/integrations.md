# Integrasi

[English](../integrations.md) · [Bahasa Indonesia](integrations.md)

InterrupThink berintegrasi pada batas host. Framework dapat menyediakan pesan,
node, agent, task, atau retrieval; floor penalaran semantik tetap berupa
`run_session`.

Framework opsional bukan dependency inti. Instal dengan `pip` di environment
terisolasi saat menjalankan contoh tertentu. Instalasi library dan suite test
default harus tetap dapat digunakan tanpa framework tersebut.

## Host Python native

Pola native adalah integrasi referensi:

```python
from interrupthink import LlmMonitor, run_session

result = run_session(llm=specialist_llm, monitor=LlmMonitor(), tool=tool)
```

Untuk pipeline dua specialist, host menjalankan satu sesi untuk retrieval dan
hanya memulai sesi writer ketika sesi pertama diizinkan untuk melanjutkan. Host
meneruskan konteks yang disetujui; host tidak membuat saluran interupsi
simetris antarspecialist.

Lihat [`../../cases/two-specialists/`](../../cases/two-specialists/).

## LangGraph

Letakkan `run_session` di node agent atau specialist dan pertahankan graph host
serta `ToolNode` pada batas normalnya. Interupsi batas tool graph dapat tetap
menjadi lapisan pertahanan kedua, tetapi bukan floor penalaran semantik.

```bash
pip install langgraph
python3 cases/langgraph-apply/run.py
python3 cases/langgraph-correct/run.py
```

Lihat [`../../cases/langgraph-node/`](../../cases/langgraph-node/) untuk host test,
[`../../cases/langgraph-apply/`](../../cases/langgraph-apply/) untuk contoh freeze
`ToolNode` 1:1, dan
[`../../cases/langgraph-correct/`](../../cases/langgraph-correct/) untuk
koreksi-lalu-lanjut.

## LangChain

Gunakan LangChain untuk prompt, riwayat pesan, atau wrapper tool, dan panggil
`run_session` untuk slot penalaran. Contoh tidak menggunakan `AgentExecutor`
sebagai pengganti floor.

```bash
pip install langchain
python3 cases/langchain-specialist/run.py
python3 cases/langchain-correct/run.py
python3 cases/langchain-chat/run.py
```

Lihat [`../../cases/langchain-specialist/`](../../cases/langchain-specialist/),
[`../../cases/langchain-correct/`](../../cases/langchain-correct/), dan
[`../../cases/langchain-chat/`](../../cases/langchain-chat/).

## LlamaIndex

Gunakan retriever framework untuk retrieval dan masukkan hasilnya ke sesi.
Contoh saat ini menggunakan `VectorStoreIndex.as_retriever().retrieve`;
framework `QueryEngine` tidak digunakan sebagai loop penalaran.

```bash
pip install llama-index llama-index-llms-openai
python3 cases/llamaindex-retrieve/run.py
```

Lihat [`../../cases/llamaindex-retrieve/`](../../cases/llamaindex-retrieve/).

## CrewAI

CrewAI dapat memberi label pada satu peran atau dua peran berurutan dengan
`Agent`, `Task`, dan `Crew`. `run_session` tetap menjadi loop penalaran.
`Crew.kickoff` tidak digunakan sebagai pengganti floor, dan contoh tidak
mengaktifkan delegasi hierarkis.

```bash
pip install crewai
python3 cases/crewai-pipe/run.py
python3 cases/crewai-correct/run.py
```

Lihat [`../../cases/crewai-pipe/`](../../cases/crewai-pipe/) dan
[`../../cases/crewai-correct/`](../../cases/crewai-correct/).

## AutoGen

AutoGen dapat memberi label pada satu `ConversableAgent` atau dua peran
berurutan. Contoh saat ini menetapkan `human_input_mode="NEVER"` dan memanggil
`run_session` untuk slot penalaran. Contoh tidak menggunakan `initiate_chat`
sebagai loop penalaran maupun `UserProxyAgent` sebagai mekanisme interupsi
semantik.

```bash
pip install autogen
python3 cases/autogen-pipe/run.py
python3 cases/autogen-correct/run.py
```

Lihat [`../../cases/autogen-pipe/`](../../cases/autogen-pipe/) dan
[`../../cases/autogen-correct/`](../../cases/autogen-correct/).

## Handoff bernama di dalam framework

Framework mempertahankan node, peran, pesan, atau indeksnya. `run_session`
tetap menilai specialist. Ketika hasil menyebut penerima, host menyusun
`Escalation`, `Consult`, atau `Takeover` dan membuka langkah berikutnya.
Handoff, delegasi, chat engine, atau group chat milik framework tidak membuat
pilihan tersebut.

| Host | Rute | Yang ditunjukkan folder |
|---|---|---|
| LangGraph | Escalation | [`cases/langgraph-offer/`](../../cases/langgraph-offer/): node dealer memeriksa harga yang tercantum; node policy menerima paket; tawaran satu dolar tidak di-commit |
| LangChain | Consultation | [`cases/langchain-rule/`](../../cases/langchain-rule/): checker menerima aturan yang diposting; patch kembali ke chat yang sama |
| CrewAI | Escalation | [`cases/crewai-order/`](../../cases/crewai-order/): peran counter menerima paket pesanan; `place_order` tidak berjalan |
| AutoGen | Takeover ke `human` | [`cases/autogen-support/`](../../cases/autogen-support/): manusia menerima paket; tidak ada agent kedua yang melanjutkan |
| LlamaIndex | Consultation | [`cases/llamaindex-page/`](../../cases/llamaindex-page/): checker menerima satu halaman hasil retrieval; assistant yang sama hanya melanjutkan sejauh halaman itu |

Setiap folder memiliki rutenya sendiri. Call site singkat berada di bawah
[`examples/`](../../examples/). Instal framework dalam virtual environment saat
menjalankan folder terkait. Jangan menambahkannya ke package inti.

## Batas integrasi

Contoh integrasi menunjukkan wiring, bukan penggantian framework. Contoh tidak
mengklaim InterrupThink mewarisi jaminan framework terkait keandalan,
observability, persistensi, atau deployment.

Hasil sesi membawa prefix dan watermark. Host menyimpannya di checkpointer atau
queue miliknya sendiri. InterrupThink tetap menjadi floor 1:1 di dalam proses
yang memanggil `run_session`. InterrupThink tidak mengimpor graph checkpointer
dan tidak memulihkan proses yang crash.
