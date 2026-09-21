# Keterbatasan

[English](../limitations.md) · [Bahasa Indonesia](limitations.md)

InterrupThink masih merupakan library eksperimental. Bukti saat ini berguna
untuk memeriksa kontrak floor, tetapi belum cukup untuk memutuskan deployment
produksi.

## Keterbatasan evaluasi

- Sebagian besar test memakai fixture sintetis dan respons `FakeLlm`
  deterministik.
- Jalur yang diizinkan adalah kontrol lokal, bukan baseline kualitas model.
- Smoke test live bersifat nondeterministik dan bergantung pada provider,
  prompt, versi model, jaringan, serta kredensial.
- Belum ada confidence interval, seed acak dari percobaan berulang, latency,
  throughput, atau
  pengukuran biaya.
- Test framework bergantung pada versi package di environment dan dapat
  di-skip.
- Tidak ada klaim perbandingan dengan sistem orkestrasi lain.

## Keterbatasan runtime

- Resume adalah request baru dengan watermark, bukan KV-cache rewind.
- Koreksi dan lanjut baru dibuktikan pada fixture sintetis; ini bukan klaim
  bahwa interupsi selalu meningkatkan akurasi model.
- Rollback belum menyediakan checkpoint terdistribusi atau pemulihan proses.
- `LlmMonitor` live adalah panggilan HTTP blocking per `ThoughtUnit`. Generate
  dan supervisi tidak berjalan tumpang tindih.
- Permintaan specialist live tidak mengaktifkan kelanjutan di latar belakang.
  `cancel_ok` mencatat keberhasilan HTTP cancel, bukan bahwa generate
  berhenti di provider.
- `Unknown` adalah state default monitor. Ini konservatif, tetapi dapat melewatkan
  masalah jika bukti tidak tersedia.
- Parsing langkah semantik bergantung pada specialist yang menghasilkan dokumen
  terstruktur sesuai format.
- Verdict monitor bukan bukti bahwa jawaban pasti benar.

## Keterbatasan efek samping

- Contoh memakai dummy tool, file lokal, dan sandbox path.
- Tidak ada repository Git, database, email provider, deployment system, atau
  vector database eksternal yang dimodifikasi oleh case yang terdokumentasi.
- Path guard tidak melindungi host dari proses yang sudah disusupi.
- Otorisasi tool, kredensial, retry, idempotensi, dan transaksi tetap menjadi
  tanggung jawab aplikasi host.
- Mengosongkan `tool_policy` (`tool_policy=None`) adalah allow-if-Ok untuk
  demo dan contoh OSS. Itu bukan otorisasi produksi. Tool berkonsekuensi
  membutuhkan policy host yang eksplisit. `reversible` dari model bukan
  otorisasi host.

## Batas cakupan

Library ini tidak mencakup UI, voice/VAD, mesh multi-agent simetris,
pengiriman hidden chain-of-thought, atau layanan produksi hosted.
