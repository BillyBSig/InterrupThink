# Reproducibility

[English](../reproducibility.md) · [Bahasa Indonesia](reproducibility.md)

Hasil publik terikat pada source code, test, asumsi environment, dan kelas
bukti yang dinyatakan. Menjalankan ulang hanya klaim dalam prosa tidak cukup.

## Environment

- Python: 3.11 atau lebih baru
- Dependency inti: environment source yang di-commit
- Framework opsional: dipasang terpisah di environment test
- Test deterministik: tidak memerlukan API key
- Jalur smoke live: hanya kredensial provider pribadi; bukan kredensial proyek

Buat environment terisolasi dan instal package inti:

```bash
uv venv
uv pip install -e ".[dev]"
```

Framework host opsional bukan bagian dari himpunan dependency inti. Instal
hanya package yang diperlukan oleh case yang direproduksi:

```bash
uv pip install langgraph
uv pip install langchain
uv pip install llama-index llama-index-llms-openai
uv pip install crewai
uv pip install autogen
```

## Pemeriksaan deterministik

Jalankan pemeriksaan kontrak inti:

```bash
python3 docs/check_publication.py
python3 -m pytest tests/test_public_api.py tests/test_library_packaging.py tests/test_wheel_install.py -x --tb=short -q
python3 -m pytest tests/test_sandbox_write.py tests/test_correct_resume.py tests/test_spike_paths.py -x --tb=short -q
python3 -m pytest tests/test_two_specialists.py tests/test_false_policy.py tests/test_deny_answer_pipeline.py -x --tb=short -q
python3 -m pytest tests/test_llm_monitor.py tests/test_run_session_contract.py -x --tb=short -q
python3 -m pytest tests/test_supervisor_escalation.py tests/test_supervisor_consult.py tests/test_supervisor_takeover.py tests/test_supervisor_handoff.py -q
```

Jalankan pemeriksaan host opsional setelah package-nya terinstal:

```bash
python3 -m pytest tests/test_langgraph_node.py tests/test_langgraph_apply.py tests/test_langgraph_correct.py -q
python3 -m pytest tests/test_langchain_extra.py tests/test_langchain_chat.py tests/test_langchain_correct.py -q
python3 -m pytest tests/test_llamaindex_extra.py -q
python3 -m pytest tests/test_crewai_extra.py tests/test_crewai_correct.py tests/test_autogen_extra.py tests/test_autogen_correct.py -q
python3 -m pytest tests/test_langgraph_offer_case.py tests/test_langchain_rule_case.py tests/test_crewai_order_case.py tests/test_autogen_support_case.py tests/test_llamaindex_page_case.py -q
```

Suite lengkapnya adalah:

```bash
python3 -m pytest -q
```

## Catatan bukti

Saat melaporkan hasil reproduksi, sertakan:

1. revisi source atau commit;
2. sistem operasi;
3. versi Python;
4. perintah instalasi package;
5. versi framework opsional;
6. perintah test atau case yang tepat;
7. status keluar dan artefak yang diamati;
8. apakah hasilnya berupa bukti deterministik atau model live.

Jangan sertakan API key, prompt privat, trace model mentah, atau nilai
environment pribadi dalam laporan.

## Perbedaan adalah bukti yang berguna

Jika reproduksi berbeda, pertahankan kegagalan dan laporkan artefak berguna
yang paling kecil: perintah, environment, nama test, exception, dan apakah
dependency opsional terinstal. Jangan diam-diam mengubah hasil yang diharapkan
agar run berhasil.
