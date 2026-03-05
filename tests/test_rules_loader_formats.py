from pathlib import Path

import pytest

from triage.rules_engine import load_knowledge_base


ROOT = Path(__file__).resolve().parents[1]


def test_loader_supports_json_and_yaml() -> None:
    kb_v1 = load_knowledge_base(str(ROOT / "knowledge_base" / "chest_pain_rules_v0_1.json"))
    kb_v2 = load_knowledge_base(str(ROOT / "knowledge_base" / "chest_pain_rules_v0_2.yaml"))

    assert kb_v1.engine_mode == "v1"
    assert kb_v2.engine_mode == "v2"
    assert kb_v2.default_profile == "outpatient_adult"


def test_loader_error_contains_path_version_and_error_at(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad_rules.yaml"
    bad_file.write_text(
        "\n".join(
            [
                'version: "0.2"',
                "strength_scale:",
                "  weak: { lr: 1.5 }",
                "profiles:",
                "  p1:",
                "    priors: { ACS: 0.03 }",
                "evidence_rules:",
                "  - id: E1",
                "    when: { field: unknown_field, op: eq, value: true }",
                "    affects:",
                "      ACS: { direction: support, strength: weak }",
                "output_mapping:",
                "  hypothesis_to_department: { ACS: cardiology }",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc:
        load_knowledge_base(str(bad_file))

    msg = str(exc.value)
    assert "file=" in msg
    assert "version=0.2" in msg
    assert "error_at=" in msg
