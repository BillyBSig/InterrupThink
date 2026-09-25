# Protokol evaluasi

[English](../evaluation.md) · [Bahasa Indonesia](evaluation.md)

## Tujuan

Evaluasi saat ini mengajukan dua pertanyaan kontrak:

> Dapatkah host **menghentikan** langkah semantik yang tidak didukung sebelum
> efek sampingnya di-commit?
>
> Setelah pemutusan, dapatkah host **mengoreksi** reasoning process (patch +
> watermark) dan **melanjutkan** dengan rollback, alih-alih hanya membatalkan
> atau memulai ulang dari awal?

Ini adalah contract verification untuk library floor, bukan benchmark
Language Model quality, latency, throughput, atau agent performance secara
umum.

Contract check tambahan mencakup named receiver. Escalation, consultation,
dan takeover mempertahankan status `Ok` serta menyertakan nama pada hasil.
Test memeriksa siapa yang menerima paket, langkah mana yang tetap ada di
dalamnya, dan apakah jawaban pertama di-commit. Test tidak menilai prosa
penerima.

## Desain perbandingan

Setiap case dengan efek samping memiliki jalur kontrol:

- **interrupt path** — premise yang salah atau tidak didukung terdeteksi
  sebelum tool, sink jawaban, atau sesi downstream;
- **correct-and-resume path** — setelah pemutusan, patch diterapkan dan
  specialist melanjutkan dari checkpoint (`rollback`);
- **allow path** — task dengan bentuk yang sama berjalan saat tidak ada
  interupsi.

Allow path adalah serial/local control comparison. Claim dibatasi pada side
effect dan session behavior yang diamati dalam fixture.

## Kelas bukti

### Deterministic contract test

Evidence utama menggunakan `FakeLlm`, scripted monitor, sandbox tool, dan
fixture kecil. Test ini dapat diulang dan tidak memerlukan API key.

Test memverifikasi:

- semantic unit yang di-parse dan monitor verdict;
- urutan interupsi;
- ada atau tidaknya sandbox side effect;
- field rollback event;
- behavior optional dependency;
- instalasi local wheel.

### Live smoke path

Command-line case runner dapat menggunakan `LiveLlm` dan `LlmMonitor` dengan
environment file pribadi. Setiap live monitor verdict menunggu provider
sebelum sesi berlanjut. Run ini menunjukkan wiring ke live model, tetapi
bersifat nondeterministic dan tidak digunakan untuk mengklaim model accuracy.

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

Optional framework test akan di-skip dengan benar ketika package-nya tidak
ada. Jika framework terpasang di environment, jalankan test file terkait:

```bash
python3 -m pytest tests/test_langgraph_node.py tests/test_langgraph_apply.py tests/test_langgraph_correct.py -q
python3 -m pytest tests/test_langchain_extra.py tests/test_langchain_chat.py tests/test_langchain_correct.py -q
python3 -m pytest tests/test_llamaindex_extra.py -q
python3 -m pytest tests/test_crewai_extra.py tests/test_crewai_correct.py tests/test_autogen_extra.py tests/test_autogen_correct.py -q
```

Versi Python yang tepat, keadaan package, dan revisi source harus disertakan
pada setiap hasil yang dilaporkan secara eksternal. Lihat
[Reproducibility](reproducibility.md).

## Kriteria pass

Skenario hanya dilaporkan pass apabila kontrak utamanya diamati:

- interupsi terjadi sebelum efek samping yang dilindungi;
- setelah koreksi, resume melanjutkan dari watermark, bukan hanya membatalkan
  sesi;
- allow/control path menghasilkan side effect terbatas yang diharapkan;
- hasil sesi mencatat data interupsi atau rollback yang diharapkan;
- optional host package tidak menjadi core dependency;
- test dapat dipetakan ke source test atau case yang di-commit.

Jika dependency tidak tersedia, hasilnya adalah `not evaluated` atau
`skipped`, bukan status pass yang disimpulkan dari inspeksi source.

## Disiplin pelaporan

Hasil publik membedakan:

- deterministic test evidence dari live smoke evidence;
- kontrak skenario dari production guarantee;
- local control comparison dari benchmark baseline;
- test yang pass dari framework atau deployment mode yang belum diuji.

Hasil tidak menyertakan prompt privat, respons model mentah, nilai environment,
trace yang dihasilkan, atau identifier riset internal.
