from pathlib import Path

from triage.rules_engine import load_knowledge_base, triage_from_rules
from triage.schemas import ChestPainAnswers


ROOT = Path(__file__).resolve().parents[1]


def test_missing_critical_questions_upgrade_to_urgent() -> None:
    kb = load_knowledge_base(str(ROOT / "knowledge_base" / "chest_pain_rules_v0_2.yaml"))
    triage = triage_from_rules(kb, ChestPainAnswers(), profile_id="outpatient_adult")

    assert triage.level == "URGENT"
    assert "sob" in triage.missing_critical_questions
    assert "syncope" in triage.missing_critical_questions
    assert any("保守升级" in reason for reason in triage.reasons)
