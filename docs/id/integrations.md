# Integrasi

[English](../integrations.md) · [Bahasa Indonesia](integrations.md)

InterrupThink berintegrasi di batas host. Framework dapat menyediakan pesan,
node, agent, task, atau retrieval; thinking floor tetap dijalankan melalui
`run_session`.

Framework opsional bukan dependensi inti. Instal framework di environment
terpisah jika ingin menjalankan contoh tertentu.

## Host Python biasa

Pola dasar:

```python
from interrupthink import LlmMonitor, run_session

result = run_session(llm=specialist_llm, monitor=LlmMonitor(), tool=tool)
```

Untuk pipeline dengan dua specialist, host menjalankan sesi retrieval terlebih
dahulu. Sesi writer baru dimulai setelah konteks dari sesi pertama diizinkan.

## LangGraph

Letakkan `run_session` di dalam node specialist dan pertahankan `ToolNode`
di batas host. Interupsi pada batas tool LangGraph dapat menjadi pemeriksaan
lapis kedua, tetapi bukan pengganti thinking floor semantik.

```bash
pip install langgraph
python3 cases/langgraph-correct/run.py
```

## LangChain

Gunakan LangChain untuk prompt, riwayat pesan, atau wrapper tool, lalu panggil
`run_session` untuk giliran penalaran.

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
langkah penalaran sebelum tindakan berikutnya.

## CrewAI

CrewAI dapat mengatur satu atau beberapa peran secara berurutan. Thinking
floor tetap dijalankan dari masing-masing peran.

```bash
pip install crewai
python3 cases/crewai-correct/run.py
```

## AutoGen

AutoGen dapat mengatur `ConversableAgent`, sementara `run_session` tetap
menjadi batas pemeriksaan langkah semantik.

```bash
pip install autogen
python3 cases/autogen-correct/run.py
```

## Batas integrasi

Framework host menyediakan struktur aplikasi, bukan keputusan thinking floor.
Host tetap bertanggung jawab atas kredensial, retry, idempotensi, transaksi,
serta efek samping eksternal.

Hasil sesi membawa prefix dan watermark. Host menyimpan keduanya di
checkpointer atau antriannya sendiri. InterrupThink tetap menjadi floor 1:1
di dalam proses yang memanggil `run_session`. Paket ini tidak mengimpor
checkpointer milik graf dan tidak memulihkan proses yang sudah mati.
