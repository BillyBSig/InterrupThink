# Kebijakan dokumentasi publik

[English](../PUBLICATION_POLICY.md) · [Bahasa Indonesia](PUBLICATION_POLICY.md)

Direktori `docs/` adalah batas dokumentasi publik dalam repository sumber
InterrupThink. README di root, `cases/`, `examples/`, dan docstring library
juga merupakan materi untuk pengguna. Materi tersebut dikurasi bagi pembaca
yang perlu memahami dan mereproduksi library, bukan untuk menerbitkan
keseluruhan catatan riset internal.

## Konten yang diizinkan

Tambahkan konten jika:

- ditulis dalam bahasa Inggris;
- bermanfaat bagi pengguna library, evaluator, atau kontributor;
- didukung oleh kode sumber, test yang telah di-commit, atau hasil run yang
  telah disanitasi;
- dapat direproduksi tanpa kredensial privat;
- menjelaskan cakupan, ketidakpastian, dan keterbatasan secara tegas;
- tidak memuat prompt privat, trace mentah model, atau data pribadi.

Halaman evaluasi publik boleh menjelaskan skenario, metode, hasil yang
diamati, test sumber, dan keterbatasan. Halaman tersebut tidak boleh mengubah
satu fixture menjadi klaim umum tentang keamanan atau kualitas.

## Konten yang dikecualikan

Jangan menyalin hal berikut ke `docs/`:

- rencana internal, gate, identifier tugas, identifier kartu eksperimen, atau
  label singkat yang hanya bermakna dalam catatan riset;
- file lab lokal yang tidak dipublikasikan (`plan/`, termasuk
  `plan/STATUS.md` dan `plan/AGENTS.md`);
- prompt mentah, memo privat, penalaran tersembunyi, atau transkrip model;
- file `.env`, API key, token, sertifikat, atau path kredensial;
- artefak `runs/`, `tmp/`, log, cache, atau environment lokal yang dihasilkan;
- nama pribadi, detail infrastruktur privat, atau informasi pelanggan;
- keputusan arsitektur yang belum diterbitkan atau status proyek internal;
- klaim tanpa test, catatan run, atau prosedur yang dapat direproduksi.

Catatan riset tetap bersifat internal. Dokumentasi publik harus merangkum
bukti tanpa membocorkan koordinasi atau perencanaan privat dalam catatan
tersebut.

## Daftar periksa peninjauan

Sebelum menerbitkan perubahan:

- [ ] Halaman berbahasa Inggris dan memiliki pembaca yang jelas.
- [ ] Setiap klaim angka atau perilaku memiliki test sumber atau catatan run.
- [ ] Halaman membedakan test deterministik dari pemeriksaan model live.
- [ ] Halaman menyatakan batasan dan kondisi yang belum diuji.
- [ ] Tidak ada identifier internal atau konten riset privat.
- [ ] Markdown dan docstring untuk pengguna memakai penjelasan sederhana,
      bukan label laboratorium atau nomor tugas.
- [ ] Tidak ada nilai mirip secret atau artefak yang dihasilkan.
- [ ] Link dan code block telah diperiksa dari root repository.
- [ ] Seluruh diff hanya berisi perubahan dokumentasi yang dimaksud.

## Kebijakan koreksi

Jika hasil publik keliru, perbaiki halaman dan sertakan penjelasan singkat
dalam pesan commit. Jangan menulis ulang hasil yang gagal seolah-olah berhasil.
Jika test sumber atau protokol berubah, perbarui metode dan batasan secara
bersamaan.
