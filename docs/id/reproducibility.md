# Reproducibility

[English](../reproducibility.md) · [Bahasa Indonesia](reproducibility.md)

Tujuan reproducibility adalah membantu orang lain membedakan hasil yang berasal
dari source code, test deterministik, dan model live.

## Environment

Catat informasi berikut:

- versi Python;
- sistem operasi;
- commit source;
- versi dependency;
- apakah framework opsional terpasang;
- apakah test memakai `FakeLlm` atau model live.

Buat environment yang terisolasi dari root repository:

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

Jangan commit `.env`, API key, atau output lokal.

## Pemeriksaan deterministik

Jalankan test kontrak tanpa API key:

```bash
python3 -m pytest tests/test_public_api.py tests/test_library_packaging.py -x --tb=short -q
python3 -m pytest tests/test_sandbox_write.py tests/test_correct_resume.py -q
python3 -m pytest tests/test_two_specialists.py tests/test_deny_answer_pipeline.py -q
```

Jika framework opsional tidak tersedia, test terkait boleh di-skip. Laporkan skip
sebagai `not evaluated`, bukan sebagai hasil positif.

## Smoke test live

Salin `.env.example` menjadi `.env`, isi kredensial secara lokal, lalu jalankan
case yang ingin diuji:

```bash
cp .env.example .env
python3 cases/correct-resume/run.py
```

Hasil live dipengaruhi model, prompt, network, dan waktu. Jangan gunakan satu
run live sebagai benchmark kualitas model.

## Catatan bukti

Setiap hasil yang dibagikan sebaiknya mencatat:

- command yang dijalankan;
- source revision;
- versi Python dan dependency;
- input atau fixture;
- jalur yang diuji;
- hasil yang diamati;
- keterbatasan dan hal yang belum diuji.

Jangan bagikan respons mentah model, prompt privat, token, path kredensial,
atau data pribadi.

## Perbedaan juga merupakan bukti

Perbedaan antara environment atau model tidak perlu disembunyikan. Catat
perbedaan tersebut dan jelaskan apakah perbedaan itu dapat memengaruhi hasil.
