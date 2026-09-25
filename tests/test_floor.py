from src.eval.osaka_trap import uses_public_spike_as_demand
from src.parse.steps import ThoughtUnit, parse_steps
from src.runtime.events import Patch, Verdict
from src.runtime.floor import Floor


def _unit(seq: int, kind: str, text: str, parent: str = "tu_00") -> ThoughtUnit:
    return ThoughtUnit(
        id=f"tu_{seq:02d}",
        agent="B",
        parent_id=parent,
        kind=kind,
        text=text,
    )


def test_rollback_drops_tail_and_prefix_omits_dropped_text():
    floor = Floor(rewrite_kept=uses_public_spike_as_demand)
    plan = _unit(1, "plan", "keep this plan")
    premise = _unit(2, "premise", "Q3 Japan is the annual trend", "tu_01")
    claim = _unit(3, "claim", "year is a boom", "tu_02")
    evidence = _unit(4, "evidence", "tail must vanish", "tu_03")
    for unit in (plan, premise, claim, evidence):
        floor.ingest(unit)

    patch = Patch(
        from_agent="A",
        target_unit_id="tu_02",
        rollback_to="tu_01",
        diagnosis="bad premise",
        missing="FY rolling baseline",
        directive="resume from plan",
        preserve=["tu_01"],
    )
    action = floor.apply_verdict(
        Verdict(
            unit_id="tu_02",
            status="False",
            reason="trap",
            patch=patch,
            rollback_to="tu_01",
        )
    )
    assert action.abort is True
    assert action.interrupt_id
    assert action.dropped_ids == ["tu_02", "tu_03", "tu_04"]
    prefix = floor.resume_prefix()
    assert "keep this plan" in prefix
    assert "Q3 Japan" not in prefix
    assert "year is a boom" not in prefix
    assert "tail must vanish" not in prefix
    assert "FY rolling baseline" in prefix
    assert "<supervisor_patch>" not in prefix


def test_resume_rewrites_kept_wrong_premise():
    floor = Floor(rewrite_kept=uses_public_spike_as_demand)
    floor.ingest(_unit(1, "plan", "keep this plan"))
    floor.ingest(_unit(2, "premise", "Q3 +42% is demand", "tu_01"))
    floor.ingest(_unit(3, "claim", "open the warehouse", "tu_02"))
    patch = Patch(
        from_agent="A",
        target_unit_id="tu_03",
        rollback_to="tu_02",
        diagnosis="bad",
        missing="FY rolling 12-month Osaka volume is -4%",
        directive="use FY rolling",
        preserve=["tu_02"],
    )
    floor.apply_verdict(
        Verdict(unit_id="tu_03", status="False", reason="trap", patch=patch, rollback_to="tu_02")
    )
    prefix = floor.resume_prefix()
    assert "keep this plan" in prefix
    assert "open the warehouse" not in prefix
    assert "+42" not in prefix
    assert "FY rolling 12-month Osaka volume is -4%" in prefix
    assert "<supervisor_patch>" not in prefix
    assert floor.units[-1].text == "FY rolling 12-month Osaka volume is -4%"


def test_patch_aborts_and_keeps_injected_fact():
    floor = Floor()
    floor.ingest(_unit(1, "plan", "plan"))
    action = floor.apply_verdict(
        Verdict(
            unit_id="tu_01",
            status="Patch",
            patch=Patch(
                from_agent="A",
                target_unit_id="tu_01",
                rollback_to=None,
                diagnosis="nudge",
                missing="use staging, not production",
                directive="keep going",
            ),
        )
    )
    assert action.abort is True
    assert action.interrupt_id
    assert floor.cancelled is True
    assert len(floor.patches) == 1
    prefix = floor.resume_prefix()
    assert "use staging, not production" in prefix
    assert "plan" in prefix


def test_unknown_and_ok_do_not_cut():
    floor = Floor()
    floor.ingest(_unit(1, "plan", "plan"))
    unknown = floor.apply_verdict(Verdict(unit_id="tu_01", status="Unknown"))
    ok = floor.apply_verdict(Verdict(unit_id="tu_01", status="Ok"))
    assert unknown.abort is False
    assert ok.abort is False
    assert floor.units[0].state == "checked_ok"
    assert floor.watermarks.checked_ok == "tu_01"


def test_interrupt_ids_unique():
    floor = Floor()
    floor.ingest(_unit(1, "plan", "a"))
    floor.ingest(_unit(2, "premise", "b", "tu_01"))
    first = floor.cancel("one")
    floor.cancelled = False
    floor.ingest(_unit(3, "claim", "c", "tu_01"))
    second = floor.cancel("two")
    assert first != second
    assert floor.interrupt_ids == [first, second]


def test_default_floor_does_not_rewrite_q3_text():
    floor = Floor()
    floor.ingest(_unit(1, "plan", "keep this plan"))
    floor.ingest(_unit(2, "premise", "Q3 +42% is demand", "tu_01"))
    floor.ingest(_unit(3, "claim", "open the warehouse", "tu_02"))
    patch = Patch(
        from_agent="A",
        target_unit_id="tu_03",
        rollback_to="tu_02",
        diagnosis="bad",
        missing="FY rolling 12-month Osaka volume is -4%",
        directive="use FY rolling",
        preserve=["tu_02"],
    )
    floor.apply_verdict(
        Verdict(unit_id="tu_03", status="False", reason="trap", patch=patch, rollback_to="tu_02")
    )
    prefix = floor.resume_prefix()
    assert "Q3 +42% is demand" in prefix
    assert floor.units[-1].text == "Q3 +42% is demand"


def test_resume_prefix_keeps_plain_text():
    floor = Floor()
    floor.ingest(_unit(1, "plan", "keep a < b & c"))
    prefix = floor.resume_prefix()
    assert "plan: keep a < b & c" in prefix
    assert "&amp;" not in prefix
    doc = parse_steps(prefix)
    assert doc.units[0].text == "keep a < b & c"
