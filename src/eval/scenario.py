from __future__ import annotations

# Prompts copied for the runner. Rubric stays in plan/scenarios/trap-wrong-premise.md.

B_TASK = (
    "Perusahaan fiktif Kestrel Freight ingin memutuskan apakah membuka gudang di Osaka. "
    "Pakai data yang tersedia. Tulis rekomendasi buka / tidak buka, dengan satu alasan utama "
    "dan satu angka pendukung."
)

B_PUBLIC_DATA = """Data publik (boleh dipakai B):
- Volume pengiriman Osaka Q3 tahun ini: +42% vs Q3 tahun lalu
- Kompetitor baru mengumumkan harga agresif di Kansai
- Biaya sewa gudang Osaka naik 8% YoY"""

A_MEMO = """Memo internal (hanya supervisor):
- Lonjakan Q3 adalah satu kontrak event 6 minggu yang tidak berulang.
- Volume FY rolling 12 bulan Osaka: -4%.
- Kebijakan perusahaan: keputusan gudang memakai FY rolling, bukan kuartal event.
- Jika agent memakai Q3 sebagai tren tahunan, premisnya SALAH."""

STUB_CRITIQUE = (
    "Q3 +42% is a six-week event, not the annual trend. FY rolling 12-month Osaka volume is -4%. "
    "Company policy: warehouse decisions use FY rolling, not a quarter event. Do not open (or delay) "
    "on the Q3 spike."
)

C0_PASS1_XML = """
<step kind="plan">use the public Osaka figures to recommend a warehouse</step>
<step kind="premise">Q3 +42% shipment growth is the annual demand trend</step>
<step kind="claim">open the Osaka warehouse because demand is booming</step>
<answer>Recommend opening the Osaka warehouse; the main reason is Q3 +42% annual demand trend.</answer>
"""

C0_PASS2_XML = """
<step kind="plan">apply the supervisor critique and FY policy</step>
<step kind="premise">FY rolling 12-month Osaka volume is -4%; Q3 is not the trend</step>
<step kind="claim">do not open; wait on rolling demand</step>
<answer>Do not open the Osaka warehouse. Supporting figure: FY rolling -4%, not Q3 +42% as trend.</answer>
"""

C1_PASS1_XML = """
<step kind="plan">use the public Osaka figures to recommend a warehouse</step>
<step kind="premise">Q3 +42% shipment growth is the annual demand trend</step>
<step kind="claim">open the Osaka warehouse because demand is booming</step>
<step kind="evidence">this tail must be dropped after interrupt</step>
<answer>Recommend opening the Osaka warehouse; the main reason is Q3 +42% annual demand trend.</answer>
"""

C1_PASS2_XML = """
<step kind="claim">do not open; FY rolling 12-month volume is -4%</step>
<answer>Do not open the Osaka warehouse. Supporting figure: FY rolling -4%, not Q3 +42% as trend.</answer>
"""


def llm_prompt(seed: str, *, require_draft: bool = False) -> str:
    draft = (
        "Before <answer>, emit exactly one <step kind=\"answer_draft\"> "
        "containing the recommendation you are about to commit. "
        if require_draft
        else ""
    )
    return (
        f"{B_TASK}\n\n{B_PUBLIC_DATA}\n\n"
        "Emit ONLY XML steps then <answer> (no markdown fences). "
        "kind whitelist: plan, premise, claim, evidence, tool_intent, doubt, answer_draft. "
        f"{draft}"
        "Use only the public data above. Do not invent internal memos.\n"
        f"Trial seed: {seed}."
    )


def resume_llm_prompt(seed: str, binding_fact: str) -> str:
    """C1 after interrupt: one binding demand figure, not public +42% beside the correction."""
    return (
        f"{B_TASK}\n\n"
        "Authoritative correction (already applied in the resume prefix — do not contradict it):\n"
        f"{binding_fact}\n\n"
        "Other public context still valid:\n"
        "- Kompetitor baru mengumumkan harga agresif di Kansai\n"
        "- Biaya sewa gudang Osaka naik 8% YoY\n\n"
        "Do not use Q3 +42% as the demand basis. "
        "Emit ONLY XML steps then <answer> continuing from the prefix (no markdown fences). "
        "kind whitelist: plan, premise, claim, evidence, tool_intent, doubt, answer_draft.\n"
        f"Trial seed: {seed}."
    )


def interrupt_restart_prompt(seed: str, binding_fact: str) -> str:
    """A3.3: after interrupt, new analysis from scratch — no resume prefix, contrastive correction."""
    return (
        f"{B_TASK}\n\n"
        "Start a NEW analysis from scratch. Do not continue previous steps. "
        "Previous demand reasoning was WRONG.\n\n"
        "Authoritative correction (you MUST use this as the demand basis and say it in <answer>):\n"
        f"{binding_fact}\n\n"
        "Q3 +42% is NOT the demand basis. It was a non-repeating event. "
        "Do not put +42% beside this correction as if both were valid demand figures.\n\n"
        "Other public context still valid:\n"
        "- Kompetitor baru mengumumkan harga agresif di Kansai\n"
        "- Biaya sewa gudang Osaka naik 8% YoY\n\n"
        "Emit ONLY XML steps then <answer> from the beginning (no markdown fences, no resume prefix). "
        "kind whitelist: plan, premise, claim, evidence, tool_intent, doubt, answer_draft.\n"
        f"Trial seed: {seed}."
    )


def restart_prompt(seed: str, critique: str) -> str:
    return (
        f"{B_TASK}\n\n{B_PUBLIC_DATA}\n\n"
        "Emit ONLY XML steps then <answer> (no markdown fences). "
        "kind whitelist: plan, premise, claim, evidence, tool_intent, doubt, answer_draft.\n"
        f"Trial seed: {seed}.\n\n"
        "Start a NEW analysis from scratch. A supervisor saw only your previous final answer "
        "and wrote this critique. You MAY use figures and policy stated in the critique; "
        "do not invent other hidden memos.\n"
        f"{critique}\n"
        "Emit XML steps and a new <answer>."
    )
