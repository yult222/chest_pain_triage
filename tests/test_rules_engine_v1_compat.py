from pathlib import Path

from triage.rules_engine import load_knowledge_base, triage_from_rules
from triage.schemas import ChestPainAnswers


ROOT = Path(__file__).resolve().parents[1]


def test_v1_routine_compat() -> None:
    kb = load_knowledge_base(str(ROOT / "knowledge_base" / "chest_pain_rules_v0_1.json"))
    triage = triage_from_rules(kb, ChestPainAnswers())

    assert triage.engine_mode == "v1"
    assert triage.level == "ROUTINE"
    assert triage.profile_id is None
    assert isinstance(triage.score_breakdown, dict)


def test_v1_red_flag_still_emergency() -> None:
    kb = load_knowledge_base(str(ROOT / "knowledge_base" / "chest_pain_rules_v0_1.json"))
    answers = ChestPainAnswers(
        pain_quality="压榨/紧缩",
        radiation="是",
        sob="是",
    )
    triage = triage_from_rules(kb, answers)

    assert triage.level == "EMERGENCY"
    assert triage.red_flags
    assert triage.recommended_departments
