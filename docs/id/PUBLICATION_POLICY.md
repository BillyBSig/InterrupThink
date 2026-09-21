# Kebijakan dokumentasi publik

[English](../PUBLICATION_POLICY.md) · [Bahasa Indonesia](PUBLICATION_POLICY.md)

Direktori `docs/` adalah batas dokumentasi publik di dalam repository sumber
InterrupThink. Root README, `cases/`, `examples/`, dan docstring library juga
merupakan materi yang dapat dibaca user.

## Isi yang boleh

Tambahkan materi jika:

- ditulis dengan bahasa yang jelas;
- berguna bagi user library, evaluator, atau contributor;
- didukung source code, test yang sudah di-commit, atau hasil yang sudah
  disanitasi;
- dapat direproduksi tanpa kredensial pribadi;
- menjelaskan cakupan, ketidakpastian, dan keterbatasan;
- tidak memuat prompt privat, raw trace model, atau data pribadi.

Halaman hasil boleh menjelaskan skenario, metode, hasil yang diamati, source
test, dan keterbatasan. Jangan mengubah satu fixture menjadi klaim umum
tentang keamanan atau kualitas.

## Isi yang dikecualikan

Jangan salin:

- dokumen rencana internal, gate, task identifier, atau experiment card;
- file notebook lokal yang tidak dipublikasikan;
- prompt privat, memo internal, hidden reasoning, atau transkrip model;
- `.env`, API key, token, certificate, atau path kredensial;
- artefak `runs/`, `tmp/`, log, cache, atau environment lokal;
- nama pribadi, detail infrastructure privat, atau data customer;
- keputusan arsitektur yang belum dipublikasikan;
- klaim tanpa test atau prosedur yang dapat direproduksi.

## Checklist peninjauan

- [ ] Halaman memiliki pembaca yang jelas.
- [ ] Klaim perilaku memiliki source test atau hasil.
- [ ] Test deterministik dibedakan dari model live.
- [ ] Keterbatasan disebutkan.
- [ ] Tidak ada identifier internal atau konten riset privat.
- [ ] Tidak ada nilai yang tampak seperti secret.
- [ ] Link dan code block diperiksa dari root repository.

## Koreksi dokumentasi

Jika hasil publik ternyata salah, perbaiki halaman dan jelaskan perubahan
secara singkat dalam pesan commit. Jangan mengubah hasil gagal menjadi
seolah-olah berhasil. Jika protokol atau source test berubah, perbarui metode
dan keterbatasan secara bersamaan.
