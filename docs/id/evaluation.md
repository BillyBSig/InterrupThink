# Protokol evaluasi

[English](../evaluation.md) · [Bahasa Indonesia](evaluation.md)

## Tujuan

Evaluasi saat ini mengajukan dua pertanyaan kontrak:

> Dapatkah host **menghentikan** langkah semantik yang tidak didukung sebelum
> efek sampingnya di-commit?
>
> Setelah pemutusan, dapatkah host **mengoreksi** proses penalaran (patch +
> watermark) dan **melanjutkan** dengan rollback, alih-alih hanya membatalkan
> atau memulai ulang dari awal?

Ini adalah verifikasi kontrak untuk library floor, bukan benchmark kualitas
language model, latency, throughput, atau performa agent secara umum.

Pemeriksaan kontrak tambahan mencakup penerima bernama. Escalation,
konsultasi, dan takeover mempertahankan status `Ok` serta mencantumkan nama
pada hasil. Test memeriksa siapa yang menerima paket, langkah mana yang tetap
ada di dalamnya, dan apakah jawaban pertama di-commit. Test tidak menilai
prosa penerima.

## Desain perbandingan

Setiap case dengan efek samping memiliki jalur kontrol:

- **jalur interupsi** — premise yang salah atau tidak didukung terdeteksi
  sebelum tool, sink jawaban, atau sesi downstream;
- **jalur koreksi-dan-lanjut** — setelah pemutusan, patch diterapkan dan
  specialist melanjutkan dari checkpoint (`rollback`);
- **jalur izinkan** — tugas dengan bentuk yang sama berjalan saat tidak ada
  interupsi.

Jalur izinkan adalah perbandingan serial/kontrol lokal. Klaim dibatasi pada
efek samping dan perilaku sesi yang diamati dalam fixture.

## Kelas bukti

### Test kontrak deterministik

Bukti utama menggunakan `FakeLlm`, monitor scripted, sandbox tool, dan fixture
kecil. Test ini dapat diulang dan tidak memerlukan API key.

Test memverifikasi:

- unit semantik yang diparse dan verdict monitor;
- urutan interupsi;
- ada atau tidaknya efek samping sandbox;
- field event rollback;
- perilaku dependency opsional;
- instalasi wheel lokal.

### Jalur smoke live

Runner case command-line dapat menggunakan `LiveLlm` dan `LlmMonitor` dengan
file environment pribadi. Setiap verdict monitor live menunggu provider
sebelum sesi berlanjut. Run ini menunjukkan wiring terhadap model live, tetapi
tidak deterministik dan tidak digunakan untuk mengklaim akurasi model.

Tidak ada API key proyek yang diperlukan ataupun disimpan. Kredensial tidak
boleh di-commit.

## Perintah reproduksi

Dari root source repository:

```bash
uv venv
uv pip install -e ".[dev]"
python3 docs/check_publication.py
python3 -m pytest tests/test_public_api.py tests/test_library_packaging.py tests/test_wheel_install.py -x --tb=short -q
python3 -m pytest tests/test_sandbox_write.py tests/test_correct_resume.py tests/test_spike_paths.py -x --tb=short -q
python3 -m pytest tests/test_two_specialists.py tests/test_false_policy.py tests/test_deny_answer_pipeline.py -x --tb=short -q
python3 -m pytest tests/test_llm_monitor.py tests/test_run_session_contract.py -x --tb=short -q
```

Test framework opsional akan di-skip dengan benar ketika package-nya tidak
ada. Jika framework terpasang di environment, jalankan file test terkait:

```bash
python3 -m pytest tests/test_langgraph_node.py tests/test_langgraph_apply.py tests/test_langgraph_correct.py -q
python3 -m pytest tests/test_langchain_extra.py tests/test_langchain_chat.py tests/test_langchain_correct.py -q
python3 -m pytest tests/test_llamaindex_extra.py -q
python3 -m pytest tests/test_crewai_extra.py tests/test_crewai_correct.py tests/test_autogen_extra.py tests/test_autogen_correct.py -q
```

Versi Python yang tepat, keadaan package, dan revisi source harus disertakan
pada setiap hasil yang dilaporkan secara eksternal. Lihat
[Reproducibility](reproducibility.md).

## Kriteria lulus

Skenario hanya dilaporkan lulus apabila kontrak utamanya diamati:

- interupsi terjadi sebelum efek samping yang dilindungi;
- setelah koreksi, resume melanjutkan dari watermark, bukan hanya membatalkan
  sesi;
- jalur izinkan/kontrol menghasilkan efek samping terbatas yang diharapkan;
- hasil sesi mencatat data interupsi atau rollback yang diharapkan;
- package host opsional tidak menjadi dependency inti;
- test dapat dipetakan ke source test atau case yang di-commit.

Jika dependency tidak tersedia, hasilnya adalah `not evaluated` atau
`skipped`, bukan keberhasilan yang disimpulkan dari inspeksi source.

## Disiplin pelaporan

Hasil publik membedakan:

- bukti test deterministik dari bukti smoke live;
- kontrak skenario dari jaminan produksi;
- perbandingan kontrol lokal dari benchmark baseline;
- test yang lulus dari framework atau mode deployment yang belum diuji.

Hasil tidak menyertakan prompt privat, respons model mentah, nilai environment,
trace yang dihasilkan, atau identifier riset internal.
