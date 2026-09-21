# Hasil

[English](../results.md) · [Bahasa Indonesia](results.md)

Halaman ini merangkum bukti kontrak saat ini. Ini bukan benchmark produk.
Setiap hasil menjelaskan fixture, jalur kontrol, dan efek samping yang
dilindungi.

## Ringkasan

### Pipeline dua sesi native

- **Metode:** `FakeLlm` deterministik, monitor scripted, satu sesi retrieval,
  lalu sesi writer yang hanya berjalan jika diizinkan.
- **Hasil:** klaim retrieval yang stale dihentikan sebelum writer dimulai;
  jalur tanpa interupsi menjalankan dua sesi dan membuat satu file keputusan.
- **Bukti:** `tests/test_two_specialists.py`,
  `cases/two-specialists/`.
- **Batas:** data retrieval berupa fixture lokal, bukan basis pengetahuan live.

### Perlindungan penulisan sandbox

- **Metode:** sesi deterministik dengan filesystem sandbox.
- **Hasil:** jalur yang diinterupsi tidak membuat file; jalur yang diizinkan menulis
  satu file di dalam sandbox; traversal keluar sandbox ditolak.
- **Bukti:** `tests/test_sandbox_write.py`, `cases/freeze-write/`.
- **Batas:** sandbox bukan batas keamanan untuk proses yang sudah disusupi.

### Koreksi dan lanjut

- **Metode:** sesi dua request dengan premise yang dikoreksi.
- **Hasil:** file produksi yang keliru tidak dibuat, event resume mencatat
  `rollback`, dan file staging dapat ditulis.
- **Bukti:** `tests/test_correct_resume.py`,
  `cases/correct-resume/`.
- **Batas:** fixture ini tidak membuktikan peningkatan akurasi model secara
  umum.

### Pencegahan jawaban yang tidak valid

- **Metode:** specialist menyiapkan jawaban, lalu langkah pengiriman hanya
  dimulai jika jawaban diterima.
- **Hasil:** jawaban dengan klaim kebijakan yang tidak didukung tidak mencapai
  outbox.
- **Bukti:** `tests/test_false_policy.py`,
  `tests/test_deny_answer_pipeline.py`.
- **Batas:** outbox adalah file lokal, bukan email atau messaging service.

### Integrasi framework

Case LangGraph, LangChain, LlamaIndex, CrewAI, dan AutoGen menjaga
`run_session` sebagai thinking floor sambil memakai struktur host masing-masing.
Test framework bersifat opsional dan dapat di-skip jika package tidak tersedia.

### Supervisor dan state netral

Monitor mengizinkan state `Unknown` sebagai default. Response supervisor yang
malformed tidak otomatis dianggap sebagai interupsi.

### Packaging

Import publik dan wheel lokal diperiksa oleh test packaging. Paket ini belum
dipublikasikan sebagai release PyPI.

## Interpretasi

Bukti ini mendukung kontrak lokal tentang blocking, koreksi, rollback, dan
integrasi host. Bukti ini tidak mendukung klaim production readiness,
sertifikasi keamanan, atau keunggulan dibandingkan model/framework lain.
