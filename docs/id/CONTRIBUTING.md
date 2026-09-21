# Kontribusi dokumentasi

[English](../CONTRIBUTING.md) · [Bahasa Indonesia](CONTRIBUTING.md)

Dokumentasi dipelihara bersama repository sumber, tetapi memiliki pembaca dan
batas publikasi sendiri.

## Sebelum mengedit

Baca:

- [`README.md`](README.md) untuk cakupan publik;
- [`PUBLICATION_POLICY.md`](PUBLICATION_POLICY.md) untuk aturan isi;
- [`evaluation.md`](evaluation.md) sebelum menambahkan klaim hasil.

Jangan menyalin dokumen perencanaan internal ke dokumentasi publik. Gunakan
source test dan hasil yang sudah disanitasi sebagai bukti.

## Perubahan berbasis bukti

Setiap klaim baru sebaiknya menyertakan:

1. perilaku yang terlihat oleh user;
2. test atau command yang dapat dijalankan ulang;
3. hasil yang diamati;
4. keterbatasan dan cakupan;
5. perbedaan antara bukti deterministik dan model live.

Jika bukti belum tersedia, tulis `not evaluated`, bukan menebak.

## Pemeriksaan lokal

Dari root repository:

```bash
python3 -m pytest tests/test_public_api.py tests/test_library_packaging.py -x --tb=short -q
python3 -m pytest -q
python3 docs/check_publication.py
```

Test framework opsional dapat di-skip ketika paket belum diinstal. Skip tersebut
tidak boleh ditulis sebagai hasil framework yang lulus.

## Gaya penulisan

- Gunakan bahasa yang langsung dan mudah dipahami.
- Letakkan tindakan user sebelum detail implementasi.
- Gunakan section pendek dan command yang dapat dijalankan.
- Jelaskan istilah saat pertama kali digunakan.
- Nyatakan apa yang belum dibuktikan.
- Hindari identifier internal dan bahasa status proyek.

## Pull request

Perubahan dokumentasi sebaiknya menjelaskan pembaca yang dituju, source code atau
test pendukung, hal yang sengaja dikecualikan, dan pemeriksaan lokal yang
dijalankan.

Jangan sertakan kredensial, trace mentah, prompt privat, atau artefak hasil
generate.

Kontribusi dokumentasi mengikuti [Apache License, Version 2.0](../../LICENSE).
