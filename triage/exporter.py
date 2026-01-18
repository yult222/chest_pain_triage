from __future__ import annotations

import io
import json
from datetime import datetime
from typing import Tuple

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

from .schemas import CaseRecord


def export_case_json(case: CaseRecord) -> bytes:
    return json.dumps(case.model_dump(), ensure_ascii=False, indent=2, default=str).encode("utf-8")


def export_case_pdf(case: CaseRecord) -> bytes:
    """Generate a simple A4 PDF summary.

    Uses CID font for CJK (STSong-Light). You can replace with a local font if needed.
    """
    buffer = io.BytesIO()

    # Register Chinese font (built-in CID font)
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        font_name = "STSong-Light"
    except Exception:
        font_name = "Helvetica"

    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    margin_x = 18 * mm
    y = height - 20 * mm

    def draw_line(text: str, dy: float = 6.5 * mm, size: int = 11):
        nonlocal y
        c.setFont(font_name, size)
        c.drawString(margin_x, y, text)
        y -= dy

    created = case.created_at.strftime("%Y-%m-%d %H:%M")

    draw_line("胸痛智能分诊 - 结构化病例摘要", size=14, dy=10 * mm)
    draw_line(f"生成时间: {created}")
    draw_line(f"规则版本: {case.rules_version}")
    draw_line("-")

    p = case.patient
    draw_line("【基本信息】", size=12)
    draw_line(f"姓名: {p.name or '未填'}    性别: {p.sex or '未填'}    年龄: {p.age if p.age is not None else '未填'}")
    draw_line(f"联系方式: {p.phone or '未填'}")

    a = case.answers
    draw_line("-")
    draw_line("【症状要点（问卷）】", size=12)
    draw_line(f"疼痛部位: {a.pain_location or '未选'}    疼痛评分: {a.pain_severity if a.pain_severity is not None else '未填'}/10")
    draw_line(f"起病突然: {a.sudden_onset}    疼痛性质: {a.pain_quality}")
    draw_line(f"放射痛: {a.radiation}    气促: {a.sob}    大汗/恶心: {a.sweat_nausea}")
    draw_line(f"晕厥/近晕厥: {a.syncope}    卒中样症状: {a.neuro_deficit}")

    draw_line("-")
    draw_line("【填空题原文】", size=12)
    text = (case.free_text.symptom_text or "").strip() or "（未填写）"
    # Wrap long text
    max_chars = 40
    for i in range(0, len(text), max_chars):
        draw_line(text[i : i + max_chars], dy=6.0 * mm)

    t = case.triage
    draw_line("-")
    draw_line("【分诊结果】", size=12)
    draw_line(f"分诊级别: {t.level}")
    draw_line("推荐科室（按优先级）: " + " -> ".join(t.recommended_departments))

    if t.red_flags:
        draw_line("红旗征触发:")
        for rf in t.red_flags:
            draw_line(f"- {rf.name}: {rf.message}", dy=6.0 * mm, size=10)

    if case.llm_summary_for_doctor:
        draw_line("-")
        draw_line("【给医生的接诊摘要（LLM生成）】", size=12)
        s = case.llm_summary_for_doctor
        for i in range(0, len(s), max_chars):
            draw_line(s[i : i + max_chars], dy=6.0 * mm)

    c.showPage()
    c.save()

    return buffer.getvalue()


def export_case(case: CaseRecord) -> Tuple[bytes, bytes]:
    return export_case_json(case), export_case_pdf(case)
