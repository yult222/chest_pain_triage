from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


YesNo = Literal["未选择", "否", "是"]



class PatientInfo(BaseModel):
    name: Optional[str] = Field(None, description="可选，用于病例导出")
    sex: Optional[Literal["男", "女", "其他/不便透露"]] = None
    age: Optional[int] = Field(None, ge=0, le=120)
    phone: Optional[str] = Field(None, description="可选")


class ChestPainAnswers(BaseModel):
    """Structured questionnaire answers.

    NOTE: This is v0.1 schema; you can extend fields as you add questions.
    """

    pain_location: Optional[str] = Field(None, description="3D人体点击返回的区域名")
    pain_severity: Optional[int] = Field(None, ge=0, le=10, description="0-10")

    # Onset / quality
    sudden_onset: YesNo = "否"
    pain_quality: Literal[
        "未选择",
        "压榨/紧缩",
        "压迫感/沉重感",
        "刺痛/针扎",
        "烧灼/反酸样",
        "刀割/撕裂",
        "闷痛",
        "不确定/描述不上来",
    ] = "未选择"

    tearing_pain: YesNo = "未选择"  # for dissection-like description

    # Triggers / relief
    exertional: YesNo = "未选择"  # triggered by exertion
    relieved_by_rest: YesNo = "未选择"
    after_meal: YesNo = "未选择"
    relieved_by_antacid: YesNo = "未选择"
    worse_with_movement: YesNo = "未选择"
    reproducible: YesNo = "未选择"  # reproducible by pressing / moving

    # Associated symptoms
    radiation: YesNo = "未选择"
    sob: YesNo = "未选择"  # shortness of breath
    sweat_nausea: YesNo = "未选择"  # diaphoresis / nausea
    palpitations: YesNo = "未选择"
    syncope: YesNo = "未选择"  # fainting / near syncope
    neuro_deficit: YesNo = "未选择"  # stroke-like symptoms
    pleuritic: YesNo = "未选择"  # worse with deep breath / cough
    cough_fever: YesNo = "未选择"
    hemoptysis: YesNo = "未选择"
    vomiting: YesNo = "未选择"

    # Risk factors
    risk_cad: YesNo = "未选择"  # HTN/DM/HLD/smoking/family hx/known CAD, etc.
    immobilization: YesNo = "未选择"  # recent surgery/immob/long travel
    leg_swelling: YesNo = "未选择"  # DVT sign

    # Special
    trauma: YesNo = "未选择"
    panic: YesNo = "未选择"  # panic-like symptoms
    stress_trigger: YesNo = "未选择"  # stress trigger
    heartburn: YesNo = "未选择"  # classic reflux


class FreeTextInput(BaseModel):
    symptom_text: str = Field("", description="用户填空题描述")


class RedFlagHit(BaseModel):
    id: str
    name: str
    message: str


class TriageResult(BaseModel):
    level: Literal["EMERGENCY", "URGENT", "ROUTINE"]
    recommended_departments: List[str]
    department_details: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    red_flags: List[RedFlagHit] = Field(default_factory=list)
    score_breakdown: Dict[str, float] = Field(default_factory=dict)
    reasons: List[str] = Field(default_factory=list)


class LLMExtraction(BaseModel):
    """LLM-extracted structure from free text.

    IMPORTANT: The model MUST NOT fabricate. Unknown => null/empty.
    """

    chief_complaint: Optional[str] = None
    hpi: Optional[str] = None
    key_symptoms: List[str] = Field(default_factory=list)
    negated_symptoms: List[str] = Field(default_factory=list)
    onset_time: Optional[str] = None
    risk_factors: List[str] = Field(default_factory=list)
    meds: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    notes_for_doctor: Optional[str] = None


class CaseRecord(BaseModel):
    """Final exportable case record."""

    created_at: datetime = Field(default_factory=datetime.utcnow)
    product: str = "ChestPain-Triage-MVP"
    rules_version: str = "0.1"

    patient: PatientInfo
    answers: ChestPainAnswers
    free_text: FreeTextInput

    triage: TriageResult
    llm_extraction: Optional[LLMExtraction] = None
    llm_summary_for_patient: Optional[str] = None
    llm_summary_for_doctor: Optional[str] = None

