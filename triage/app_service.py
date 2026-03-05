from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional

from .config import settings
from .rules_engine import KnowledgeBase, triage_from_rules
from .schemas import CaseRecord, ChestPainAnswers, FreeTextInput, PatientInfo, TriageResult

ProgressCallback = Callable[[str], None]


@dataclass
class RealtimeAlert:
    active: bool
    hits: list[str]
    signature: Optional[str]
    should_popup: bool
    triage_preview: TriageResult


@dataclass
class GenerationResult:
    case: CaseRecord
    triage: TriageResult
    top3_departments: list[str]
    llm_enabled: bool


def detect_text_red_flags(text: str) -> list[str]:
    """Lightweight keyword alerts from free text (high-sensitivity reminders)."""
    t = (text or "").strip()
    if not t:
        return []

    def has_kw(keyword: str) -> bool:
        if re.search(rf"(无|没有|否认).{{0,3}}{re.escape(keyword)}", t):
            return False
        return keyword in t

    hits: list[str] = []
    if any(has_kw(k) for k in ["晕厥", "昏厥", "晕倒", "眼前发黑", "快要晕"]):
        hits.append("文本提示：胸痛伴晕厥/近晕厥")
    if any(has_kw(k) for k in ["口齿不清", "说话困难", "偏侧无力", "偏瘫", "一侧麻木", "视物困难"]):
        hits.append("文本提示：胸痛伴神经功能缺失（卒中样）")
    if any(has_kw(k) for k in ["撕裂", "刀割"]):
        hits.append("文本提示：撕裂/刀割样剧痛（需急评估）")
    if any(has_kw(k) for k in ["呼吸困难", "气促", "喘不过气"]):
        hits.append("文本提示：胸痛伴呼吸困难/气促")
    if has_kw("咯血"):
        hits.append("文本提示：出现咯血")
    if any(has_kw(k) for k in ["剧烈呕吐", "反复呕吐"]):
        hits.append("文本提示：剧烈/反复呕吐后胸痛（需急评估）")

    return hits


def evaluate_realtime_alert(
    kb: KnowledgeBase,
    answers_preview: ChestPainAnswers,
    symptom_text: str,
    shown_signature: Optional[str],
    profile_id: Optional[str] = None,
) -> RealtimeAlert:
    triage_preview = triage_from_rules(kb, answers_preview, profile_id=profile_id)
    hits = [f"{rf.name}（{rf.message}）" for rf in triage_preview.red_flags]
    hits += detect_text_red_flags(symptom_text)

    if not hits:
        return RealtimeAlert(
            active=False,
            hits=[],
            signature=None,
            should_popup=False,
            triage_preview=triage_preview,
        )

    signature = "|".join(sorted(hits))
    return RealtimeAlert(
        active=True,
        hits=hits,
        signature=signature,
        should_popup=signature != shown_signature,
        triage_preview=triage_preview,
    )


def generate_case_record(
    kb: KnowledgeBase,
    patient: PatientInfo,
    answers: ChestPainAnswers,
    symptom_text: str,
    profile_id: Optional[str] = None,
    has_key: Optional[bool] = None,
    progress: Optional[ProgressCallback] = None,
) -> GenerationResult:
    def notify(message: str) -> None:
        if progress:
            progress(message)

    has_key = bool(settings.api_key) if has_key is None else has_key

    notify("规则引擎计算中...")
    triage = triage_from_rules(kb, answers, profile_id=profile_id)
    top3_departments = triage.recommended_departments[:3]

    llm_extraction = None
    patient_summary = None
    doctor_summary = None
    llm_enabled = False

    if has_key:
        try:
            from .llm import extract_structured, generate_summaries

            notify("正在抽取结构化信息（LLM）...")
            llm_extraction = extract_structured(symptom_text, answers)

            notify("正在生成患者/医生摘要（LLM）...")
            patient_summary, doctor_summary = generate_summaries(
                symptom_text=symptom_text,
                answers=answers,
                triage_level=triage.level,
                dept_names=top3_departments,
                red_flags=[rf.name for rf in triage.red_flags],
            )
            llm_enabled = True
        except Exception:
            # Keep a rules-only result if LLM dependency or request fails.
            llm_extraction = None
            patient_summary = None
            doctor_summary = None
            llm_enabled = False

    notify("正在组装病例...")
    case = CaseRecord(
        patient=patient,
        answers=answers,
        free_text=FreeTextInput(symptom_text=symptom_text or ""),
        triage=triage,
        llm_extraction=llm_extraction,
        llm_summary_for_patient=patient_summary,
        llm_summary_for_doctor=doctor_summary,
        rules_version=kb.version,
        rules_profile=triage.profile_id,
    )
    notify("生成完成")

    return GenerationResult(
        case=case,
        triage=triage,
        top3_departments=top3_departments,
        llm_enabled=llm_enabled,
    )
