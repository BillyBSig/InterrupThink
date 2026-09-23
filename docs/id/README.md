# Dokumentasi InterrupThink

*Interruptible Reasoning at Thought Units (IRTU)*

[English](../README.md) · [Bahasa Indonesia](README.md)

InterrupThink adalah library Python open-source eksperimental untuk
menginterupsi **dan mengoreksi** proses penalaran pada batas semantik
`ThoughtUnit`, bukan pada batas token mentah.

Library ini memberi aplikasi host thinking floor 1:1 yang ringkas:

1. Specialist menghasilkan langkah-langkah yang dapat diperiksa.
2. Monitor mengamati langkah-langkah tersebut.
3. Interupsi dapat **menghentikan** jalur yang tidak aman atau tidak didukung
   **serta memasukkan koreksi** (`Patch`), lalu melanjutkan dengan watermark.
4. Verdict `Ok` juga dapat menyebut penerima: escalation ke specialist
   berikutnya, consultation kembali ke specialist yang sama, atau takeover
   oleh editor atau manusia. `Escalation`, `Consult`, dan `Takeover` menyusun
   paket tersebut. Host membuka sesi berikutnya.
5. Host hanya melakukan commit pada hasil yang disetujui dan memiliki
   watermark.

Restart penuh adalah pilihan cadangan. Default yang dimaksudkan adalah
melanjutkan proses penalaran dari langkah terakhir yang diterima.

Dokumentasi ini sengaja berfokus pada bukti. Isinya menjelaskan hal-hal yang
ditunjukkan oleh implementasi dan test saat ini, yang masih eksperimental, dan
yang belum dievaluasi. Dokumentasi ini tidak mengklaim kesiapan produksi atau
kualitas model.

## Mulai cepat

Package saat ini diinstal dari source repository. Package belum dipublikasikan
ke PyPI.

```bash
uv pip install -e .
python3 examples/run_session_dummy.py
```

Surface import publik sengaja dibuat kecil:

```python
from interrupthink import LlmMonitor, ThoughtUnit, run_session
```

Mulailah dari [Mulai menggunakan](getting-started.md), lalu baca
[Konsep](concepts.md) untuk memahami interupsi, **koreksi**, dan rollback.

## Peta dokumentasi

- [Mulai menggunakan](getting-started.md) — instal, jalankan, dan periksa sesi pertama.
- [Konsep](concepts.md) — unit semantik, verdict, koreksi, rollback, handoff bernama, dan keamanan tool.
- [Integrasi](integrations.md) — host native dan contoh framework opsional.
- [Protokol evaluasi](evaluation.md) — cara klaim diuji dan dibandingkan.
- [Hasil](results.md) — ringkasan bukti publik saat ini.
- [Keterbatasan](limitations.md) — batas cakupan dan pertanyaan terbuka.
- [Reproducibility](reproducibility.md) — command, environment, dan pelaporan.
- [Kebijakan publikasi](PUBLICATION_POLICY.md) — isi yang termasuk direktori publik ini.
- [Berkontribusi](CONTRIBUTING.md) — cara menyempurnakan dokumentasi.

## Apa yang didukung oleh bukti saat ini

Test suite saat ini mendukung klaim tingkat kontrak tentang:

- memblokir tool yang tidak dapat dibatalkan sebelum dijalankan;
- mencegah jawaban yang tidak valid sampai ke sink downstream;
- **mengoreksi** premise yang salah dan melanjutkan dengan rollback (bukan
  hanya membatalkan sesi);
- menjaga integrasi framework tetap opsional;
- mempertahankan floor yang sama ketika host memakai label LangGraph, LangChain,
  LlamaIndex, CrewAI, atau AutoGen;
- memetakan verdict supervisor yang malformed ke state netral `Unknown`;
- menyerahkan pekerjaan yang dipertahankan kepada penerima bernama melalui
  escalation, consultation, atau takeover, tanpa melakukan commit pada jawaban
  yang belum selesai.

Ini adalah pemeriksaan kecil yang deterministik atau berada dalam sandbox.
Keduanya bukan benchmark produksi, sertifikasi keamanan, atau perbandingan
model bahasa.

## Cakupan dan hal yang tidak dituju

InterrupThink saat ini bukan:

- antarmuka pengguna;
- layanan orkestrasi produksi;
- mesh multi-agent dengan barge-in simetris;
- sistem voice, VAD, atau streaming audio;
- saluran untuk hidden chain-of-thought;
- controller database, email, Git, atau deployment.

Package framework opsional diinstal terpisah untuk contoh-contohnya. Package
tersebut bukan dependency inti library.

## Sumber dan lisensi

Implementasi berada di source repository yang memuat direktori ini. Mulailah
dari [README sumber](../../README.md) untuk codebase dan
[examples](../../examples/).

Hak cipta 2026 BillyBSig. Source dan dokumentasi ini dilisensikan di bawah
[Apache License, Version 2.0](../../LICENSE). Distribusikan ulang hanya sesuai
ketentuan lisensi. Publikasi ke PyPI tetap merupakan keputusan terpisah.
