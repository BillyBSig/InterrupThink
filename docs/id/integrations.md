# Integrasi

[English](../integrations.md) · [Bahasa Indonesia](integrations.md)

InterrupThink berintegrasi pada batas host. Framework dapat menyediakan
message, node, agent, task, atau retrieval; thinking floor tetap dijalankan
melalui `run_session`.

Framework opsional bukan dependency inti. Instal framework di environment
terpisah saat menjalankan contoh tertentu.

## Host Python biasa

Pola dasar:

```python
from interrupthink import LlmMonitor, run_session

result = run_session(llm=specialist_llm, monitor=LlmMonitor(), tool=tool)
```

Untuk pipeline dua specialist, host menjalankan sesi pertama untuk retrieval
dan baru memulai sesi writer setelah konteksnya diizinkan.

## LangGraph

Letakkan `run_session` di dalam node specialist dan pertahankan `ToolNode`
di batas host yang normal. Batas tool LangGraph dapat menjadi pemeriksaan
lapis kedua, tetapi bukan pengganti thinking floor semantik.

```bash
pip install langgraph
python3 cases/langgraph-correct/run.py
```

## LangChain

Gunakan LangChain untuk prompt, message history, atau wrapper tool, lalu
panggil `run_session` untuk giliran penalaran.

```bash
pip install langchain
python3 cases/langchain-correct/run.py
```

## LlamaIndex

Gunakan retriever dari LlamaIndex dan masukkan hasilnya ke sesi:

```bash
pip install llama-index llama-index-llms-openai
python3 cases/llamaindex-retrieve/run.py
```

Retrieval tetap menjadi tanggung jawab LlamaIndex; `run_session` memeriksa
proses penalaran sebelum tindakan berikutnya.

## CrewAI

CrewAI dapat mengatur satu atau beberapa role secara berurutan. Thinking floor
tetap dipanggil dari masing-masing role.

```bash
pip install crewai
python3 cases/crewai-correct/run.py
```

## AutoGen

AutoGen dapat mengatur `ConversableAgent`, sementara `run_session` tetap
menjadi batas untuk memeriksa langkah semantik.

```bash
pip install autogen
python3 cases/autogen-correct/run.py
```

## Batas integrasi

Framework host menyediakan struktur aplikasi, bukan keputusan thinking floor.
Host tetap bertanggung jawab atas kredensial, retry, idempotensi, transaksi,
dan efek samping eksternal.
