# Berkontribusi pada dokumentasi

[English](../CONTRIBUTING.md) · [Bahasa Indonesia](CONTRIBUTING.md)

Dokumentasi dipelihara bersama repository sumber, tetapi memiliki pembaca dan
batas publikasi tersendiri.

## Sebelum mengedit

Baca:

- [`README.md`](README.md) untuk memahami cakupan publik;
- [`PUBLICATION_POLICY.md`](PUBLICATION_POLICY.md) untuk aturan penyertaan
  materi;
- [`evaluation.md`](evaluation.md) sebelum menambahkan klaim tentang test.

Jangan menggunakan dokumen perencanaan internal sebagai naskah publik.
Gunakan test sumber dan hasil yang telah disanitasi sebagai bukti.

## Perubahan yang mengutamakan bukti

Untuk setiap klaim baru, sertakan:

1. perilaku yang dilihat pengguna;
2. test atau perintah yang dapat direproduksi;
3. hasil yang diamati;
4. batasan dan cakupannya;
5. perbedaan antara bukti deterministik dan bukti dari model live.

Jika bukti belum tersedia, tulis `not evaluated`, jangan menerka.

## Pemeriksaan lokal

Dari root repository sumber:

```bash
python3 -m pytest tests/test_public_api.py tests/test_library_packaging.py -x --tb=short -q
python3 -m pytest -q
python3 docs/check_publication.py
```

Test framework opsional dapat di-skip jika paketnya belum terpasang. Skip
tersebut tidak boleh dijelaskan sebagai hasil framework yang lulus.

## Gaya penulisan

- Gunakan bahasa Inggris yang sederhana dan lugas.
- Dahulukan tindakan pengguna daripada detail implementasi.
- Utamakan bagian singkat dan perintah yang dapat dijalankan.
- Jelaskan istilah saat pertama kali muncul.
- Nyatakan hal yang tidak ditunjukkan oleh bukti.
- Hindari nomor tugas internal dan bahasa status proyek.

## Pull request

Perubahan dokumentasi perlu menjelaskan:

- pembaca publik yang dilayaninya;
- kode sumber atau test yang mendukungnya;
- hal yang sengaja tidak disertakan;
- pemeriksaan lokal yang telah dijalankan.

Jangan menyertakan kredensial, trace mentah, prompt privat, atau artefak case
yang dihasilkan dalam pull request.

Kontribusi dokumentasi mengikuti [Apache License, Version 2.0](../../LICENSE).
