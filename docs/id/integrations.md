# Integrasi

[English](../integrations.md) · [Bahasa Indonesia](integrations.md)

InterrupThink berintegrasi pada batas host. Framework dapat menyediakan message,
node, agent, task, atau retrieval; semantic reasoning floor tetap berupa
`run_session`.

Optional framework bukan core dependency. Instal dengan `pip` di isolated
environment saat menjalankan example tertentu. Library installation dan
default test suite harus tetap dapat digunakan tanpa framework tersebut.

## Host Python native

Pola native adalah integrasi referensi:

```python
from interrupthink import LlmMonitor, run_session

result = run_session(llm=specialist_llm, monitor=LlmMonitor(), tool=tool)
```

Untuk pipeline dua specialist, host menjalankan satu session untuk retrieval
dan hanya memulai writer session ketika session pertama diizinkan untuk
melanjutkan. Host meneruskan context yang disetujui; host tidak membuat
saluran interupsi simetris antar-specialist.

Lihat [`../../cases/two-specialists/`](../../cases/two-specialists/).

## LangGraph

Letakkan `run_session` di agent atau specialist node dan pertahankan host graph
serta `ToolNode` pada batas normalnya. Interupsi di tool boundary graph dapat
tetap menjadi second layer of defense, tetapi bukan semantic reasoning floor.

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

Gunakan LangChain untuk prompt, message history, atau tool wrapper, lalu
panggil `run_session` untuk reasoning slot. Example tidak menggunakan
`AgentExecutor` sebagai pengganti floor.

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

Gunakan framework retriever untuk retrieval dan masukkan hasilnya ke session.
Example saat ini menggunakan `VectorStoreIndex.as_retriever().retrieve`;
framework `QueryEngine` tidak digunakan sebagai reasoning loop.

```bash
pip install llama-index llama-index-llms-openai
python3 cases/llamaindex-retrieve/run.py
```

Lihat [`../../cases/llamaindex-retrieve/`](../../cases/llamaindex-retrieve/).

## CrewAI

CrewAI dapat memberi label pada satu role atau dua role berurutan dengan
`Agent`, `Task`, dan `Crew`. `run_session` tetap menjadi reasoning loop.
`Crew.kickoff` tidak digunakan sebagai pengganti floor, dan example tidak
mengaktifkan hierarchical delegation.

```bash
pip install crewai
python3 cases/crewai-pipe/run.py
python3 cases/crewai-correct/run.py
```

Lihat [`../../cases/crewai-pipe/`](../../cases/crewai-pipe/) dan
[`../../cases/crewai-correct/`](../../cases/crewai-correct/).

## AutoGen

AutoGen dapat memberi label pada satu `ConversableAgent` atau dua role
berurutan. Example saat ini menetapkan `human_input_mode="NEVER"` dan
memanggil `run_session` untuk reasoning slot. Example tidak menggunakan
`initiate_chat` sebagai reasoning loop maupun `UserProxyAgent` sebagai
semantic interrupt mechanism.

```bash
pip install autogen
python3 cases/autogen-pipe/run.py
python3 cases/autogen-correct/run.py
```

Lihat [`../../cases/autogen-pipe/`](../../cases/autogen-pipe/) dan
[`../../cases/autogen-correct/`](../../cases/autogen-correct/).

## Handoff bernama di dalam framework

Framework mempertahankan node, role, message, atau index-nya. `run_session`
tetap mengevaluasi specialist. Ketika hasil menyebut receiver, host menyusun
`Escalation`, `Consult`, atau `Takeover` lalu membuka langkah berikutnya.
Handoff, delegation, chat engine, atau group chat milik framework tidak
membuat keputusan tersebut.

| Host | Rute | Yang ditunjukkan folder |
|---|---|---|
| LangGraph | Escalation | [`cases/langgraph-offer/`](../../cases/langgraph-offer/): node dealer memeriksa harga yang tercantum; node policy menerima paket; tawaran satu dolar tidak di-commit |
| LangChain | Consultation | [`cases/langchain-rule/`](../../cases/langchain-rule/): checker menerima aturan yang diposting; patch kembali ke chat yang sama |
| CrewAI | Escalation | [`cases/crewai-order/`](../../cases/crewai-order/): peran counter menerima paket pesanan; `place_order` tidak berjalan |
| AutoGen | Takeover ke `human` | [`cases/autogen-support/`](../../cases/autogen-support/): manusia menerima paket; tidak ada agent kedua yang melanjutkan |
| LlamaIndex | Consultation | [`cases/llamaindex-page/`](../../cases/llamaindex-page/): checker menerima satu halaman hasil retrieval; assistant yang sama hanya melanjutkan sejauh halaman itu |

Setiap folder memiliki path sendiri. Call site singkat berada di bawah
[`examples/`](../../examples/). Instal framework dalam virtual environment saat
menjalankan folder terkait. Jangan menambahkannya ke core package.

## Batas integrasi

Integration example menunjukkan wiring, bukan pengganti framework. Example
tidak mengklaim InterrupThink mewarisi jaminan framework terkait reliability,
observability, persistence, atau deployment.

Session result membawa prefix dan watermark. Host menyimpannya di
checkpointer atau queue miliknya sendiri. InterrupThink tetap menjadi floor
1:1 di dalam proses yang memanggil `run_session`. InterrupThink tidak
mengimpor graph checkpointer dan tidak melakukan process recovery.
