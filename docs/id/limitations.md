# Keterbatasan

[English](../limitations.md) · [Bahasa Indonesia](limitations.md)

InterrupThink adalah experimental library. Bukti saat ini berguna untuk
memeriksa kontrak floor, tetapi belum cukup sebagai dasar keputusan production
deployment.

## Keterbatasan evaluasi

- Sebagian besar check menggunakan fixture sintetis dan respons
  `FakeLlm` deterministik.
- Jalur allow adalah local control path, bukan baseline kualitas model.
- Smoke run model live bersifat nondeterministic dan bergantung pada provider,
  prompting, versi model, jaringan, dan kredensial.
- Hasil tidak mencakup confidence interval, random seed berulang, pengukuran
  latency, throughput, atau biaya.
- Optional framework test bergantung pada versi yang terinstal di local
  environment dan dapat di-skip bila package tidak ada.
- Tidak ada klaim di sini yang membandingkan InterrupThink dengan sistem
  orkestrasi lain.

## Keterbatasan runtime

- Resume request adalah pekerjaan baru dengan watermark, bukan KV-cache rewind.
- Koreksi-dan-lanjut ditunjukkan pada fixture sintetis. Ini bukan klaim bahwa
  interupsi secara umum meningkatkan model accuracy.
- Perilaku rollback saat ini tidak menyediakan distributed persistent
  checkpoint atau process recovery. Host dapat menyimpan prefix dan watermark
  sesi di checkpointer miliknya. Library tetap berupa floor 1:1 di dalam satu
  proses dan tidak memulihkan proses yang crash.
- Verdict `LlmMonitor` live adalah panggilan HTTP blocking untuk setiap
  `ThoughtUnit`. Generation dan supervisi tidak berjalan bersamaan.
- Request specialist live tidak mengaktifkan kelanjutan di latar belakang.
  `cancel_ok` mencatat apakah panggilan HTTP cancel berhasil, bukan apakah
  generation berhenti di provider.
- `Unknown` adalah status monitor default. Status ini konservatif, tetapi
  masalah dapat terlewat ketika monitor tidak memiliki bukti.
- Semantic-step parsing bergantung pada specialist yang menghasilkan langkah
  terstruktur sesuai harapan.
- Verdict monitor bukan bukti kebenaran.
- `Escalation`, `Consult`, dan `Takeover` menyusun teks penerima. Ketiganya
  tidak membuka sesi berikutnya. Host yang melakukannya ketika hasil menyebut
  penerima.
- Consultation mengembalikan `Patch` kepada specialist yang sama. Consultation
  tidak memindahkan ownership task.
- `takeover_to="human"` mengembalikan paket ke host. Ini tidak memulai
  specialist kedua, dan monitor tidak menulis respons orang tersebut.
- `takeover_to="editor"` menyebut specialist lain. Host dapat membuka sesi itu.
  Specialist pertama tetap tidak melanjutkan.
- Wording model live bukan kontrak handoff. Test scripted mengunci penerima,
  paket, dan apakah jawaban pertama telah di-commit.

## Keterbatasan efek samping

- Contoh menggunakan dummy tool, local file, dan sandbox path.
- Tidak ada repository Git nyata, database, provider email, sistem deployment,
  atau vector database eksternal yang dimodifikasi oleh case terdokumentasi.
- Path guard tidak melindungi dari proses yang telah dikompromikan dengan
  akses ke host.
- Tool authorization, credentials, retry, idempotency, dan transactional
  behavior tetap menjadi tanggung jawab aplikasi host.
- Tidak menyertakan `tool_policy` (`tool_policy=None`) berarti
  allow-if-Ok untuk demo dan contoh OSS. Ini bukan otorisasi produksi. Tool
  dengan konsekuensi membutuhkan policy host eksplisit. `reversible` yang
  dinyatakan model bukan otorisasi host.

## Batasan cakupan

Proyek saat ini tidak mengklaim:

- user interface atau production service;
- voice activity detection atau interupsi audio;
- barge-in simetris antarspecialist;
- mesh multi-agent (handoff bernama adalah langkah host satu arah);
- transport hidden chain-of-thought;
- orkestrasi tingkat token;
- penggantian framework;
- kesiapan rilis PyPI.

Keterbatasan ini merupakan bagian dari hasil, bukan catatan kaki yang boleh
diabaikan. Klaim baru memerlukan evaluasi terpisah dengan pertanyaan, baseline,
primary metric, dan reproduction path masing-masing.
