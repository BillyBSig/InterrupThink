from interrupthink.eval.osaka_trap import osaka_monitor, stub_supervisor_ask
from interrupthink.monitor.llm import LlmMonitor
from interrupthink.parse.steps import ThoughtUnit


def _osaka_stub() -> LlmMonitor:
    return osaka_monitor(ask=stub_supervisor_ask, budget=2)


def _unit(kind: str, text: str, uid: str = "tu_02", parent: str = "tu_01") -> ThoughtUnit:
    return ThoughtUnit(id=uid, agent="B", parent_id=parent, kind=kind, text=text)


def test_plan_is_unknown_without_calling_ask():
    calls: list[str] = []

    def ask(unit: ThoughtUnit) -> dict:
        calls.append(unit.id)
        return {"status": "False", "diagnosis": "nope"}

    monitor = LlmMonitor(ask=ask, budget=2)
    v = monitor.verdict(_unit("plan", "outline Osaka", "tu_01", "tu_00"))
    assert v.status == "Unknown"
    assert calls == []
    assert monitor.interrupts_used == 0


def test_budget_caps_false_at_two():
    n = {"i": 0}

    def ask(unit: ThoughtUnit) -> dict:
        n["i"] += 1
        return {
            "status": "False",
            "diagnosis": f"trap-{n['i']}",
            "rejects_q3_trend": True,
        }

    monitor = LlmMonitor(ask=ask, budget=2)
    first = monitor.verdict(_unit("premise", "Q3 +42% is the annual trend", "tu_02"))
    second = monitor.verdict(
        _unit("claim", "Q3 +42% annual boom continues", "tu_04", "tu_03")
    )
    third = monitor.verdict(
        _unit("premise", "Q3 +42% remains the annual trend", "tu_06", "tu_05")
    )
    assert first.status == "False"
    assert second.status == "False"
    assert third.status == "Unknown"
    assert monitor.interrupts_used == 2


def test_anti_oscillation_skips_same_diagnosis():
    monitor = _osaka_stub()
    a = monitor.verdict(_unit("premise", "Q3 +42% is the annual trend", "tu_02"))
    b = monitor.verdict(_unit("premise", "Q3 +42% is the annual trend still", "tu_03"))
    assert a.status == "False"
    assert b.status == "Unknown"
    assert monitor.interrupts_used == 1


def test_fact_mismatch_without_annual_phrase():
    monitor = _osaka_stub()
    v = monitor.verdict(
        _unit(
            "claim",
            "Rekomendasi: buka gudang. Alasan: pertumbuhan permintaan kuat, volume naik 42% YoY.",
        )
    )
    assert v.status == "False"
    assert monitor.last_rejects_q3 is True
    assert monitor.false_interrupt_count == 0


def test_rent_only_is_not_fact_mismatch():
    monitor = _osaka_stub()
    v = monitor.verdict(_unit("premise", "Sewa gudang Osaka naik 8% YoY dan kompetitor agresif."))
    assert v.status == "Unknown"
    assert monitor.interrupts_used == 0


def test_a32_askable_skips_premise_and_cuts_draft():
    calls: list[str] = []

    def ask(unit: ThoughtUnit) -> dict:
        calls.append(unit.kind)
        return {
            "status": "False",
            "diagnosis": "Q3/+42% in draft",
            "missing": "FY rolling -4%; kebijakan FY",
            "rejects_q3_trend": True,
        }

    monitor = LlmMonitor(ask=ask, budget=2, askable={"answer_draft"})
    prem = monitor.verdict(_unit("premise", "Q3 +42% is the demand basis", "tu_02"))
    draft = monitor.verdict(
        _unit("answer_draft", "Buka gudang karena Q3 +42%.", "tu_05", "tu_04")
    )
    assert prem.status == "Unknown"
    assert draft.status == "False"
    assert calls == ["answer_draft"]
    assert monitor.interrupts_used == 1


def test_a34_budget_zero_never_interrupts():
    calls: list[str] = []

    def ask(unit: ThoughtUnit) -> dict:
        calls.append(unit.id)
        return {"status": "False", "rejects_q3_trend": True}

    monitor = LlmMonitor(ask=ask, budget=0)
    v = monitor.verdict(_unit("premise", "Q3 +42% is the demand basis", "tu_02"))
    assert v.status == "Unknown"
    assert calls == []
    assert monitor.interrupts_used == 0


def test_fy_rolling_already_used_is_unknown():
    monitor = _osaka_stub()
    v = monitor.verdict(
        _unit("claim", "Jangan buka: FY rolling -4% meski Q3 +42% adalah event.")
    )
    assert v.status == "Unknown"


def test_parse_supervisor_payload_accepts_fenced_json():
    from interrupthink.monitor.verdict import parse_supervisor_payload

    payload = parse_supervisor_payload(
        """```json
{"status":"False","reason":"stale","diagnosis":"one device","missing":"multi-device","directive":"do not send","rejects_q3_trend":false}
```"""
    )
    assert payload["status"] == "False"
    assert payload["missing"] == "multi-device"
    assert payload["rejects_q3_trend"] is False


def test_parse_supervisor_payload_garbage_and_bad_status_are_unknown():
    from interrupthink.monitor.verdict import parse_supervisor_payload

    junk = parse_supervisor_payload("not json at all")
    assert junk["status"] == "Unknown"
    bad = parse_supervisor_payload('{"status":"Interrupt","reason":"x"}')
    assert bad["status"] == "Unknown"


def test_supervisor_request_uses_json_schema_format():
    from interrupthink.monitor.llm import responses_body

    body = responses_body(
        model="x",
        effort="none",
        instructions="A",
        user="unit",
        json_schema=True,
    )
    fmt = body["text"]["format"]
    assert fmt["type"] == "json_schema"
    assert fmt["strict"] is True
    assert "Unknown" in fmt["schema"]["properties"]["status"]["enum"]
    critic = responses_body(
        model="x",
        effort="none",
        instructions="A",
        user="unit",
        json_schema=False,
    )
    assert "text" not in critic


def test_pydantic_is_not_a_require_dependency():
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    pyproject = (repo / "pyproject.toml").read_text(encoding="utf-8")
    start = pyproject.index("dependencies = [")
    end = pyproject.index("]", start)
    assert "pydantic" not in pyproject[start : end + 1]


def test_llm_monitor_core_has_no_osaka_trap_defaults():
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "src" / "interrupthink" / "monitor" / "llm.py").read_text(
        encoding="utf-8"
    )
    assert "Osaka Q3" not in text
    assert "FY rolling -4%" not in text
    assert "uses_public_spike" not in text
    assert "stub_supervisor_ask" not in text
    assert "from interrupthink.eval.scenario import" not in text


def test_live_provider_has_no_osaka_or_eval_defaults():
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "src" / "interrupthink" / "providers" / "live.py").read_text(
        encoding="utf-8"
    )
    assert "osaka_trap" not in text
    assert "from interrupthink.eval" not in text
    assert "Osaka Q3" not in text
    assert "HAPPY_USER_PROMPT" not in text
    assert "INTERRUPT_USER_PROMPT" not in text


def test_runtime_core_has_no_eval_or_osaka_trap():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src" / "interrupthink"
    session = (root / "runtime" / "session.py").read_text(encoding="utf-8")
    floor = (root / "runtime" / "floor.py").read_text(encoding="utf-8")
    scripted = (root / "monitor" / "scripted.py").read_text(encoding="utf-8")
    for text in (session, floor, scripted):
        assert "from interrupthink.eval" not in text
        assert "osaka_trap" not in text
        assert "Q3 Japan" not in text
        assert "g1_live_interrupt_monitor" not in text
    assert "run_path" not in session
    assert '"q3"' not in floor.lower()
