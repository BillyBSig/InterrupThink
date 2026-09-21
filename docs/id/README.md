# Dokumentasi InterrupThink

*Interruptible Reasoning at Thought Units (IRTU)*

[English](../README.md) · [Bahasa Indonesia](README.md)

InterrupThink adalah library Python open-source eksperimental untuk
menginterupsi **dan mengoreksi** proses penalaran pada batas semantik
`ThoughtUnit`, bukan pada batas token mentah.

## Mulai cepat

```bash
uv pip install -e .
python3 examples/run_session_dummy.py
```

Import yang tersedia untuk user:

```python
from interrupthink import LlmMonitor, ThoughtUnit, run_session
```

Mulailah dari [Getting started](getting-started.md), lalu baca
[Konsep](concepts.md) untuk memahami interupsi, koreksi, rollback, dan
keamanan tool.

## Peta dokumentasi

- [Getting started](getting-started.md) — instalasi dan sesi pertama.
- [Konsep](concepts.md) — ThoughtUnit, verdict, koreksi, rollback, dan tool.
- [Integrasi](integrations.md) — host Python dan framework opsional.
- [Protokol evaluasi](evaluation.md) — cara menguji klaim.
- [Hasil](results.md) — ringkasan bukti publik.
- [Keterbatasan](limitations.md) — batas cakupan dan pertanyaan terbuka.
- [Reproducibility](reproducibility.md) — command dan lingkungan.
- [Kebijakan publikasi](PUBLICATION_POLICY.md) — isi yang boleh dipublikasikan.
- [Kontribusi](CONTRIBUTING.md) — cara memperbaiki dokumentasi.

## Apa yang didukung oleh bukti saat ini

Test suite mendukung klaim pada tingkat kontrak tentang:

- memblokir tool irreversible sebelum dijalankan;
- mencegah jawaban yang tidak valid mencapai sink downstream;
- mengoreksi premise yang salah dan melanjutkan dengan rollback;
- menjaga integrasi framework tetap opsional;
- menjaga thinking floor tetap bekerja saat host memakai framework umum;
- memetakan verdict supervisor yang malformed ke state netral `Unknown`.

Bukti ini berupa test deterministik atau sandbox kecil. Ini bukan benchmark
produksi, sertifikasi keamanan, atau perbandingan kualitas model.

## Cakupan dan hal yang tidak dituju

InterrupThink saat ini bukan:

- antarmuka pengguna;
- layanan orkestrasi produksi;
- mesh multi-agent dengan barge-in simetris;
- sistem voice, VAD, atau streaming audio;
- saluran untuk hidden chain-of-thought;
- controller database, email, Git, atau deployment.

Implementasi utama ada di repository sumber. Lihat
[README sumber](../../README.id.md) dan [examples](../../examples/).

## Sumber dan lisensi

Hak cipta 2026 BillyBSig. Kode dan dokumentasi dilisensikan di bawah
[Apache License, Version 2.0](../../LICENSE). Publikasi ke PyPI adalah
keputusan terpisah.
