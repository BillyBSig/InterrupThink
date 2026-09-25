# Hasil

[English](../results.md) · [Bahasa Indonesia](results.md)

Halaman ini adalah ringkasan public evidence untuk contract saat ini.
Scope-nya sengaja lebih sempit daripada product benchmark: setiap hasil
menjelaskan fixture, control path, dan side effect yang dilindungi.

Dua contract muncul berulang kali: **memblokir** side effect yang salah dan
**memperbaiki** reasoning lalu **melanjutkannya** (`rollback`). Cancel tanpa
resume path bukan default behavior yang dituju.

## Ringkasan

### Native two-session pipeline

- **Metode:** deterministic `FakeLlm` dan scripted monitor; satu retrieval
  session diikuti conditional writer session.
- **Hasil yang diamati:** stale retrieval claim diinterupsi sebelum writer
  dimulai; clean control path menjalankan dua session dan membuat satu
  decision file.
- **Evidence:** `tests/test_two_specialists.py`,
  `cases/two-specialists/`.
- **Batas:** retrieval data adalah local fixture, bukan production vector
  database atau live knowledge base.

### Sandbox write guard

- **Metode:** deterministic session dengan sandbox filesystem nyata.
- **Hasil yang diamati:** interrupted path tidak membuat file; allow path
  menulis satu file di dalam sandbox; traversal keluar sandbox ditolak.
- **Evidence:** `tests/test_sandbox_write.py`,
  `cases/freeze-write/`.
- **Batas:** sandbox bukan security boundary bagi proses yang tidak tepercaya.

### Correct and resume

- **Metode:** deterministic session dengan dua request dan premise yang dikoreksi.
- **Hasil yang diamati:** file produksi yang keliru tidak ada, resume event
  mencatat `rollback`, dan file staging yang sudah diperbaiki dapat ditulis.
- **Evidence:** `tests/test_correct_resume.py`,
  `cases/correct-resume/`,
  `tests/test_langchain_correct.py`,
  `cases/langchain-correct/`,
  `tests/test_langgraph_correct.py`,
  `cases/langgraph-correct/`,
  `tests/test_crewai_correct.py`,
  `cases/crewai-correct/`,
  `tests/test_autogen_correct.py`,
  `cases/autogen-correct/`.
- **Batas:** example ini memverifikasi watermark dan request flow pada floor;
  example ini tidak menyediakan general checkpoint durability atau process
  recovery.

### Pipeline penolakan jawaban

- **Metode:** host deterministik dengan sesi jawaban dan sesi outbox lanjutan.
- **Hasil yang diamati:** klaim kebijakan yang diinterupsi tidak mencapai
  outbox; jalur kontrol yang diizinkan menulis satu baris terbatas.
- **Bukti:** `tests/test_false_policy.py`,
  `tests/test_deny_answer_pipeline.py`,
  `cases/deny-answer-pipeline/`.
- **Batas:** outbox adalah file lokal, bukan penyedia email atau pesan.

### Host LangGraph

- **Metode:** test paket opsional dengan node specialist yang memanggil
  `run_session` dan `ToolNode` biasa.
- **Hasil yang diamati:** interupsi dapat melewati penulisan `ToolNode` yang
  dilindungi, dan dapat **memperbaiki** klaim host yang salah lalu melanjutkan
  sehingga `ToolNode` menulis `staging.txt`, bukan `production.txt`.
- **Bukti:** `tests/test_langgraph_node.py`,
  `tests/test_langgraph_apply.py`,
  `tests/test_langgraph_correct.py`,
  `cases/langgraph-node/`, `cases/langgraph-apply/`,
  `cases/langgraph-correct/`.
- **Batas:** framework diuji sebagai pola penyambungan host, bukan digantikan
  atau dibandingkan performanya.

### Host LangChain

- **Metode:** test paket opsional untuk specialist 1:1, riwayat chat dua giliran,
  dan wrapper yang memperbaiki lalu melanjutkan.
- **Hasil yang diamati:** interupsi dapat memblokir penulisan yang dilindungi
  atau jawaban yang tidak didukung, serta dapat **memperbaiki** klaim host yang
  salah lalu melanjutkan (`rollback`) sehingga file staging ditulis alih-alih
  file produksi.
- **Bukti:** `tests/test_langchain_extra.py`,
  `tests/test_langchain_chat.py`,
  `tests/test_langchain_correct.py`,
  `cases/langchain-specialist/`, `cases/langchain-chat/`,
  `cases/langchain-correct/`.
- **Batas:** test memakai double deterministik yang diinjeksi; test ini tidak
  mengevaluasi kualitas percakapan model.

### Retrieval LlamaIndex

- **Metode:** test paket opsional dengan `VectorStoreIndex`, embedding
  deterministik, dan `as_retriever().retrieve`.
- **Hasil yang diamati:** potongan hasil retrieval yang sudah usang
  diinterupsi sebelum `notice.txt`; jalur kontrol saat ini melakukan retrieval
  dan menulis satu pemberitahuan.
- **Bukti:** `tests/test_llamaindex_extra.py`,
  `cases/llamaindex-retrieve/`.
- **Batas:** indeks berisi satu dokumen test; tidak ada vector store eksternal
  yang dievaluasi.

### Host CrewAI dan AutoGen

- **Metode:** test paket opsional dengan peran host berurutan, sementara setiap
  slot pemikiran memanggil `run_session`. CrewAI dan AutoGen juga memiliki
  wrapper 1:1 yang memperbaiki lalu melanjutkan.
- **Hasil yang diamati:** input usang menghentikan writer sebelum
  `decision.txt`; input saat ini menjalankan dua sesi dan membuat satu file
  keputusan. Pada jalur 1:1, klaim host yang salah di-`Patch` dan
  `staging.txt` ditulis alih-alih `production.txt`.
- **Bukti:** `tests/test_crewai_extra.py`,
  `tests/test_autogen_extra.py`,
  `tests/test_crewai_correct.py`,
  `tests/test_autogen_correct.py`,
  `cases/crewai-pipe/`, `cases/autogen-pipe/`,
  `cases/crewai-correct/`, `cases/autogen-correct/`.
- **Batas:** objek framework hanyalah label dan kontainer host dalam
  eksperimen ini. Hasil ini tidak mengevaluasi orkestrasi hierarkis, group
  chat, kualitas delegasi, atau perilaku framework di produksi.

### Serah-terima bernama

- **Metode:** sesi deterministik. Monitor mengembalikan `Ok` dan nama penerima.
  `Escalation`, `Consult`, dan `Takeover` menyusun paket dari event floor.
  Folder framework opsional mengulang bentuk paket yang sama, masing-masing
  dalam satu host.
- **Hasil yang diamati:** jawaban yang belum selesai tidak di-commit. Paket
  mempertahankan task awal, receiver, alasan supervisor, langkah yang
  dipertahankan, hasil tool yang tercatat, serta panggilan yang tidak boleh
  diulang. `Escalation` tidak melanjutkan specialist pertama. `Consult`
  mengembalikan patch kepada specialist yang sama. Pengambilalihan manusia
  mengembalikan paket dan tidak memulai specialist kedua.
- **Bukti:** `tests/test_supervisor_escalation.py`,
  `tests/test_supervisor_consult.py`,
  `tests/test_supervisor_takeover.py`,
  `tests/test_supervisor_handoff.py`,
  `cases/langgraph-offer/`,
  `cases/langchain-rule/`,
  `cases/crewai-order/`,
  `cases/autogen-support/`,
  `cases/llamaindex-page/`.
- **Batas:** dokumen scripted mengunci kontrak. Sesi live dapat menunjukkan
  bahwa sesi telah dimulai dan paket telah tiba. Perumusannya bukan penilai.

### Output supervisor dan inti netral

- **Metode:** test monitor dan runtime deterministik.
- **Hasil yang diamati:** output supervisor berbentuk JSON yang ketat diterima,
  nilai status yang malformed atau tidak dikenal menjadi `Unknown`, dan inti
  runtime netral tidak membawa default khusus laboratorium. Kanal langkah
  specialist adalah baris berlabel biasa (`plan:`, `claim:`, `tool_intent:`,
  `answer:`); parser tetap menerima bentuk XML `<step>`/`<answer>` yang lama
  agar bukti yang sudah tercatat tetap bisa direproduksi.
- **Bukti:** `tests/test_llm_monitor.py`,
  `tests/test_run_session_contract.py`,
  `tests/test_spike_paths.py`.
- **Batas:** validasi skema tidak menjamin supervisor benar; validasi hanya
  membuat output malformed gagal secara tertutup ke status netral.

### Packaging

- **Metode:** membangun wheel lokal dan memasangnya dari direktori kerja bersih.
- **Hasil yang diamati:** paket `interrupthink` dapat diimpor dari wheel lokal
  tanpa akses PyPI.
- **Bukti:** `tests/test_wheel_install.py`,
  `tests/test_library_packaging.py`.
- **Batas:** ini adalah local packaging check, bukan rilis publik atau
  compatibility promise untuk semua distribusi Python.

## Interpretasi

Evidence ini mendukung reusable floor untuk **menginterupsi**, **memperbaiki**,
dan **melanjutkan** (`rollback`) pada beberapa host integration pattern.
Evidence ini tidak membuktikan bahwa interupsi meningkatkan accuracy, cost,
latency, atau user experience. Pertanyaan tersebut memerlukan eksperimen
terpisah dengan baseline, dataset, model, metric, dan uncertainty report yang
dinyatakan.
