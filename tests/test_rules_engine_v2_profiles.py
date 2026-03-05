from pathlib import Path

from triage.rules_engine import load_knowledge_base, triage_from_rules
from triage.schemas import ChestPainAnswers


ROOT = Path(__file__).resolve().parents[1]


def test_profile_changes_posterior_and_level() -> None:
    kb = load_knowledge_base(str(ROOT / "knowledge_base" / "chest_pain_rules_v0_2.yaml"))
    answers = ChestPainAnswers(
        risk_cad="是",
        sob="否",
        syncope="否",
        neuro_deficit="否",
        hemoptysis="否",
        immobilization="否",
        leg_swelling="否",
    )

    triage_outpatient = triage_from_rules(kb, answers, profile_id="outpatient_adult")
    triage_emergency = triage_from_rules(kb, answers, profile_id="emergency_adult")

    assert triage_outpatient.profile_id == "outpatient_adult"
    assert triage_emergency.profile_id == "emergency_adult"
    assert triage_emergency.posterior_breakdown["ACS"] > triage_outpatient.posterior_breakdown["ACS"]
    assert triage_outpatient.level == "URGENT"
    assert triage_emergency.level == "EMERGENCY"
