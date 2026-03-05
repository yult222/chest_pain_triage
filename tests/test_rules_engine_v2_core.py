from pathlib import Path

from triage.rules_engine import load_knowledge_base, triage_from_rules
from triage.schemas import ChestPainAnswers


ROOT = Path(__file__).resolve().parents[1]


def test_v2_posterior_threshold_triggers_emergency_without_red_flag() -> None:
    kb = load_knowledge_base(str(ROOT / "knowledge_base" / "chest_pain_rules_v0_2.yaml"))
    answers = ChestPainAnswers(
        pain_quality="压榨/紧缩",
        exertional="是",
        risk_cad="是",
        sob="否",
        syncope="否",
        neuro_deficit="否",
        hemoptysis="否",
        immobilization="否",
        leg_swelling="否",
    )
    triage = triage_from_rules(kb, answers, profile_id="outpatient_adult")

    assert triage.engine_mode == "v2"
    assert triage.level == "EMERGENCY"
    assert not triage.red_flags
    assert triage.posterior_breakdown["ACS"] >= 0.20


def test_v2_oppose_evidence_can_reduce_posterior() -> None:
    kb = load_knowledge_base(str(ROOT / "knowledge_base" / "chest_pain_rules_v0_2.yaml"))
    answers = ChestPainAnswers(
        reproducible="是",
        sob="否",
        syncope="否",
        neuro_deficit="否",
        hemoptysis="否",
        immobilization="否",
        leg_swelling="否",
    )
    triage = triage_from_rules(kb, answers, profile_id="outpatient_adult")

    assert triage.prior_breakdown["ACS"] > triage.posterior_breakdown["ACS"]
    assert any(e.rule_id == "E_REPRODUCIBLE_TENDERNESS" for e in triage.evidence_top)
