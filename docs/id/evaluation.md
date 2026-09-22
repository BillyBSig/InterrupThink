# Protokol evaluasi

[English](../evaluation.md) · [Bahasa Indonesia](evaluation.md)

## Tujuan

Evaluasi memeriksa dua kontrak:

1. Apakah host dapat menghentikan langkah semantik yang tidak didukung sebelum
   efek samping di-commit?
2. Setelah interupsi, apakah host dapat mengoreksi proses penalaran dengan patch dan
   watermark lalu melanjutkan dengan rollback?

Ini bukan benchmark kualitas model, latency, throughput, biaya, atau performa
agent secara umum.

## Desain perbandingan

Setiap case yang memiliki efek samping mencakup:

- **jalur interupsi** — premise yang salah dihentikan sebelum tool, sink jawaban,
  atau sesi downstream;
- **jalur koreksi dan lanjut** — patch diterapkan lalu request berikutnya
  melanjutkan dari checkpoint;
- **jalur yang diizinkan** — tugas yang sama berjalan tanpa interupsi.

Jalur yang diizinkan adalah pembanding serial lokal. Klaim dibatasi pada efek
samping dan perilaku sesi yang terlihat pada fixture.

## Jenis bukti

### Test kontrak deterministik

Bukti utama menggunakan `FakeLlm`, monitor scripted, sandbox tool, dan fixture
kecil. Test ini dapat diulang dan tidak membutuhkan API key.

Yang diperiksa:

- unit semantik dan verdict monitor;
- urutan interupsi;
- ada atau tidaknya efek samping pada sandbox;
- field event rollback;
- perilaku dependency opsional;
- instalasi wheel lokal.

### Live smoke path

Runner case dapat menggunakan `LiveLlm` dan `LlmMonitor` dengan `.env`
pribadi. Setiap verdict live menunggu respons provider sebelum sesi lanjut. Ini
memeriksa wiring terhadap model live, bukan akurasi model.

Credential tidak boleh di-commit.

## Command reproduksi

Dari root repository:

```bash
uv pip install -e ".[dev]"
python3 -m pytest tests/test_public_api.py tests/test_library_packaging.py -x --tb=short -q
python3 -m pytest tests/test_sandbox_write.py tests/test_correct_resume.py -x --tb=short -q
python3 -m pytest tests/test_two_specialists.py tests/test_deny_answer_pipeline.py -x --tb=short -q
```

Test framework opsional akan di-skip jika package belum tersedia:

```bash
python3 -m pytest tests/test_langgraph_node.py tests/test_langgraph_apply.py -q
python3 -m pytest tests/test_langchain_extra.py tests/test_langchain_chat.py -q
python3 -m pytest tests/test_llamaindex_extra.py -q
python3 -m pytest tests/test_crewai_extra.py tests/test_autogen_extra.py -q
```

## Kapan dianggap lulus

Case dilaporkan lulus hanya jika kontrak utamanya terlihat:

- interupsi terjadi sebelum efek samping yang dilindungi;
- setelah koreksi, resume melanjutkan dari watermark;
- jalur yang diizinkan menghasilkan efek samping terbatas yang diharapkan;
- hasil sesi mencatat data interupsi atau rollback;
- framework opsional tidak menjadi dependency inti;
- test dapat dipetakan ke source test atau case yang committed.

Jika dependency tidak tersedia, hasilnya `not evaluated` atau `skipped`, bukan
hasil positif yang disimpulkan hanya dari inspeksi source.

## Disiplin pelaporan

Hasil publik membedakan bukti test deterministik dari smoke test live,
kontrak skenario dari jaminan produksi, dan pembanding lokal dari benchmark.
Jangan menyertakan prompt privat, respons mentah model, kredensial, trace hasil
generate, atau identifier riset internal.
