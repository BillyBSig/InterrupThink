# Reproducibility

[English](../reproducibility.md) · [Bahasa Indonesia](reproducibility.md)

Public result terikat pada source code, test, environment assumption, dan
evidence class yang dinyatakan. Menjalankan ulang hanya claim dalam prosa
tidak cukup.

## Environment

- Python: 3.11 atau lebih baru
- Core dependency: environment source yang di-commit
- Optional framework: dipasang terpisah di test environment
- Deterministic test: tidak memerlukan API key
- Live smoke path: hanya provider credential pribadi; bukan project credential

Buat isolated environment dan instal core package:

```bash
uv venv
uv pip install -e ".[dev]"
```

Optional host framework bukan bagian dari core dependency set. Instal hanya
package yang diperlukan oleh case yang direproduksi:

```bash
uv pip install langgraph
uv pip install langchain
uv pip install llama-index llama-index-llms-openai
uv pip install crewai
uv pip install autogen
```

## Deterministic check

Jalankan core contract check:

```bash
python3 docs/check_publication.py
python3 -m pytest tests/test_public_api.py tests/test_library_packaging.py tests/test_wheel_install.py -x --tb=short -q
python3 -m pytest tests/test_sandbox_write.py tests/test_correct_resume.py tests/test_spike_paths.py -x --tb=short -q
python3 -m pytest tests/test_two_specialists.py tests/test_false_policy.py tests/test_deny_answer_pipeline.py -x --tb=short -q
python3 -m pytest tests/test_llm_monitor.py tests/test_run_session_contract.py -x --tb=short -q
python3 -m pytest tests/test_supervisor_escalation.py tests/test_supervisor_consult.py tests/test_supervisor_takeover.py tests/test_supervisor_handoff.py -q
```

Jalankan optional host check setelah package-nya terinstal:

```bash
python3 -m pytest tests/test_langgraph_node.py tests/test_langgraph_apply.py tests/test_langgraph_correct.py -q
python3 -m pytest tests/test_langchain_extra.py tests/test_langchain_chat.py tests/test_langchain_correct.py -q
python3 -m pytest tests/test_llamaindex_extra.py -q
python3 -m pytest tests/test_crewai_extra.py tests/test_crewai_correct.py tests/test_autogen_extra.py tests/test_autogen_correct.py -q
python3 -m pytest tests/test_langgraph_offer_case.py tests/test_langchain_rule_case.py tests/test_crewai_order_case.py tests/test_autogen_support_case.py tests/test_llamaindex_page_case.py -q
```

Full suite:

```bash
python3 -m pytest -q
```

## Evidence note

Saat melaporkan reproduction result, sertakan:

1. source revision atau commit;
2. operating system;
3. versi Python;
4. package install command;
5. optional framework version;
6. test atau case command yang tepat;
7. exit status dan artefak yang diamati;
8. apakah hasilnya deterministic evidence atau live-model evidence.

Jangan sertakan API key, private prompt, raw model trace, atau nilai
environment pribadi dalam laporan.

## Perbedaan adalah evidence yang berguna

Jika reproduction result berbeda, pertahankan failure dan laporkan artefak
berguna yang paling kecil: command, environment, test name, exception, dan
apakah optional dependency terinstal. Jangan diam-diam mengubah expected
result agar run berhasil.
