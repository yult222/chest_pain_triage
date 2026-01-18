from __future__ import annotations

import json
import re
from datetime import datetime

import streamlit as st

from triage.config import settings
from triage.exporter import export_case
from triage.llm import extract_structured, generate_summaries
from triage.rules_engine import load_knowledge_base, triage_from_rules
from triage.schemas import CaseRecord, ChestPainAnswers, FreeTextInput, PatientInfo


st.set_page_config(
    page_title="胸痛智能分诊 MVP",
    page_icon="🫀",
    layout="wide",
)


# --------------------
# Helpers
# --------------------

def tri_state(label: str, key: str, default: str = "未选择") -> str:
    """三态选择：未选择 / 否 / 是。用于支持“选择题可选”而不误判为否。"""
    options = ["未选择", "否", "是"]
    return st.radio(label, options=options, index=options.index(default), horizontal=True, key=key)


def detect_text_red_flags(text: str) -> list[str]:
    """对填空题做轻量级红旗征关键词提醒（高敏感、宁可多报）。不替代规则引擎。"""
    t = (text or "").strip()
    if not t:
        return []

    def _has_kw(kw: str) -> bool:
        # 简单否定保护：出现 “无/没有/否认 + 0~3字符 + 关键词” 认为是否定
        if re.search(rf"(无|没有|否认).{{0,3}}{re.escape(kw)}", t):
            return False
        return kw in t

    hits: list[str] = []
    if any(_has_kw(k) for k in ["晕厥", "昏厥", "昏倒", "眼前发黑", "快要晕"]):
        hits.append("文本提示：胸痛伴晕厥/近晕厥")
    if any(_has_kw(k) for k in ["口齿不清", "说话困难", "偏侧无力", "偏瘫", "一侧麻木", "视物困难"]):
        hits.append("文本提示：胸痛伴神经功能缺失（卒中样）")
    if any(_has_kw(k) for k in ["撕裂", "刀割"]):
        hits.append("文本提示：撕裂/刀割样剧痛（需急评估）")
    if any(_has_kw(k) for k in ["呼吸困难", "气促", "喘不过气"]):
        hits.append("文本提示：胸痛伴呼吸困难/气促")
    if _has_kw("咯血"):
        hits.append("文本提示：出现咯血")
    if any(_has_kw(k) for k in ["剧烈呕吐", "反复呕吐"]):
        hits.append("文本提示：剧烈/反复呕吐后胸痛（需急评估）")
    return hits


def maybe_realtime_emergency_popup(kb, answers_preview: ChestPainAnswers, symptom_text: str):
    """实时急诊弹窗：一旦检测到红旗征（规则或文本提示），无需点击生成按钮就弹窗。"""
    triage_preview = triage_from_rules(kb, answers_preview)
    hits = [f"{rf.name}（{rf.message}）" for rf in triage_preview.red_flags]
    hits += detect_text_red_flags(symptom_text)

    if not hits:
        st.session_state.pop("rf_sig_shown", None)
        st.session_state["rf_active"] = False
        return

    st.session_state["rf_active"] = True
    sig = "|".join(sorted(hits))
    # 避免每次 rerun 都重复弹
    if st.session_state.get("rf_sig_shown") != sig:
        st.session_state["rf_sig_shown"] = sig
        emergency_dialog("", hits)
    run = st.button("🧭 生成分诊建议", type="primary")
    has_key = bool(settings.api_key)

    if run:
        # （建议）避免两套数据不一致：直接用 answers_preview
        answers = answers_preview
        free_text = FreeTextInput(symptom_text=symptom_text or "")

        if hasattr(st, "status"):
            with st.status("正在生成分诊建议...", expanded=True) as status:
                status.update(label="规则引擎计算中...", state="running")
                triage = triage_from_rules(kb, answers)

                top3_depts = triage.recommended_departments[:3]

                if has_key:
                    status.update(label="正在抽取结构化信息（LLM）...", state="running")
                    llm_extraction = extract_structured(free_text.symptom_text, answers)

                    status.update(label="正在生成摘要（LLM）...", state="running")
                    patient_sum, doctor_sum = generate_summaries(
                        symptom_text=free_text.symptom_text,
                        answers=answers,
                        triage_level=triage.level,
                        dept_names=top3_depts,
                        red_flags=[rf.name for rf in triage.red_flags],
                    )
                else:
                    llm_extraction = None
                    patient_sum, doctor_sum = (None, None)

                status.update(label="生成完成", state="complete")
        else:
            with st.spinner("正在生成分诊建议..."):
                triage = triage_from_rules(kb, answers)
                top3_depts = triage.recommended_departments[:3]
                if has_key:
                    llm_extraction = extract_structured(free_text.symptom_text, answers)
                    patient_sum, doctor_sum = generate_summaries(
                        symptom_text=free_text.symptom_text,
                        answers=answers,
                        triage_level=triage.level,
                        dept_names=top3_depts,
                        red_flags=[rf.name for rf in triage.red_flags],
                    )
                else:
                    llm_extraction = None
                    patient_sum, doctor_sum = (None, None)

        # ====== 输出区域（只显示 Top3）======
        st.subheader("分诊建议")
        st.write("**推荐就诊科室（Top 3）**")
        for i, dept in enumerate(top3_depts, start=1):
            st.write(f"{i}. {dept}")

        # 你原来其它输出（解释、导出）可以继续沿用


def show_safety_banner():
    st.warning(
        "⚠️ 免责声明：本系统仅用于‘就诊科室建议/分诊辅助’，不能替代医生诊断或急救处置。"
        "如果胸痛严重或伴呼吸困难/大汗/晕厥/神经功能缺失等，请立即拨打当地急救电话或前往急诊。"
    )


def emergency_dialog(summary: str, hits: list[str]):
    # Prefer st.dialog if available
    if hasattr(st, "dialog"):
        @st.dialog("紧急提醒（请优先就医）")
        def _dlg():
            st.error("检测到可能的高危信号（红旗征）。建议立即急诊评估/呼叫急救。")
            if hits:
                st.write("**触发项：**")
                for h in hits:
                    st.write(f"- {h}")
            if summary:
                st.write("**当前症状摘要：**")
                st.write(summary)
            st.info("如果症状正在加重，请不要继续填写，优先拨打急救电话。")
        _dlg()
    else:
        st.error("检测到可能的高危信号（红旗征）。建议立即急诊评估/呼叫急救。")
        if hits:
            st.write("触发项：" + "；".join(hits))
        if summary:
            st.write("当前症状摘要：")
            st.write(summary)


# --------------------
# Sidebar config
# --------------------

with st.sidebar:
    st.header("⚙️ 配置")
    st.caption("DeepSeek 使用 OpenAI 兼容接口：base_url=https://api.deepseek.com，模型 deepseek-chat/deepseek-reasoner。")

    st.text_input("DEEPSEEK_BASE_URL", value=settings.base_url, disabled=True)
    st.text_input("DEEPSEEK_MODEL", value=settings.model, disabled=True)
    has_key = bool(settings.api_key)
    st.write("API Key 状态：" + ("✅ 已配置" if has_key else "❌ 未配置（LLM 功能将降级为仅规则分诊）"))

    st.divider()
    debug = st.toggle("显示调试信息", value=False)


# --------------------
# Main
# --------------------

st.title("🫀 胸痛智能分诊系统（MVP）")
show_safety_banner()

consent = st.checkbox("我理解并同意：该系统仅作分诊参考，不能替代医生诊断；如有急症我会优先就医/呼叫急救。", value=False)
if not consent:
    st.stop()

kb = load_knowledge_base(settings.rules_path)

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1) 基本信息")
    name = st.text_input("姓名（可选，用于导出病例）")
    sex = st.selectbox("性别（可选）", ["未填", "男", "女", "其他/不便透露"], index=0)
    age = st.number_input("年龄（可选）", min_value=0, max_value=120, value=30)
    phone = st.text_input("联系方式（可选）")

with col2:
    st.subheader("2) 疼痛位置")
    st.caption("MVP 提供可点击的简易 3D ‘数字人’组件示例（需要先构建组件）。如果暂时未构建，可用下方下拉框选择。")
    try:
        from components.body3d.body3d_component import body3d_selector

        pain_location_3d = body3d_selector(height=420, key="body3d")
    except Exception:
        pain_location_3d = None
        st.info("未检测到 3D 组件（或未构建）。可先用下拉框选择疼痛位置。")

    pain_location_fallback = st.selectbox(
        "疼痛位置（备选）",
        [
            "未选择",
            "胸骨后/正中胸口",
            "左胸",
            "右胸",
            "上腹/心窝",
            "背部/肩胛间",
            "左肩/左上肢",
            "右肩/右上肢",
        ],
        index=0,
    )


# 先填空，再选择题（选择题整体标注“可选”）
st.subheader("3) 症状补充（填空题，推荐优先填写）")
symptom_text = st.text_area(
    "请用自己的话描述胸痛：开始时间、部位、性质、持续多久、是否放射、伴随症状、既往史/用药等（可复制粘贴）。",
    height=140,
)

st.subheader("4) 症状问卷（选择题，可选）")
st.caption("可选：如果没时间可以不填/不选。系统将基于已填信息给出更保守的分诊建议；若出现高危信号会实时提醒。")

with st.expander("展开填写选择题（可选）", expanded=False):
    q1, q2, q3 = st.columns(3)
    with q1:
        pain_sev_opt = st.selectbox(
            "疼痛程度（0-10，可选）",
            options=["未选择"] + list(range(0, 11)),
            index=0,
            key="pain_sev_opt",
        )
        pain_sev = None if pain_sev_opt == "未选择" else int(pain_sev_opt)

        sudden_onset = tri_state("是否突然发生？", "sudden_onset", default="未选择")
        trauma = tri_state("是否有外伤/撞击/跌倒后出现？", "trauma", default="未选择")

    with q2:
        pain_quality = st.selectbox(
            "疼痛性质更像哪种？（可选）",
            [
                "未选择",
                "压榨/紧缩",
                "压迫感/沉重感",
                "刺痛/针扎",
                "烧灼/反酸样",
                "刀割/撕裂",
                "闷痛",
                "不确定/描述不上来",
            ],
            index=0,
            key="pain_quality",
        )
        tearing_pain = tri_state("是否明显‘撕裂/刀割样’并可放射到背部？", "tearing_pain", default="未选择")
        pleuritic = tri_state("是否深呼吸/咳嗽时更痛（胸膜性疼痛）？", "pleuritic", default="未选择")

    with q3:
        exertional = tri_state("是否运动/上楼/走快时更明显？", "exertional", default="未选择")
        relieved_by_rest = tri_state("是否休息可缓解？", "relieved_by_rest", default="未选择")
        reproducible = tri_state("按压胸壁/转动身体可诱发或复制疼痛？", "reproducible", default="未选择")

    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        sob = tri_state("是否气促/呼吸困难？", "sob", default="未选择")
        radiation = tri_state("是否放射到左臂/下颌/背部等？", "radiation", default="未选择")  # 重要：写入 answers
    with c2:
        sweat_nausea = tri_state("是否大汗/恶心/呕吐？", "sweat_nausea", default="未选择")
        palpitations = tri_state("是否心慌/心跳不齐？", "palpitations", default="未选择")
    with c3:
        syncope = tri_state("是否晕厥/眼前发黑/快要晕倒？", "syncope", default="未选择")
        neuro_deficit = tri_state("是否口齿不清/偏侧无力或麻木等？", "neuro_deficit", default="未选择")
    with c4:
        cough_fever = tri_state("是否咳嗽或发热？", "cough_fever", default="未选择")
        hemoptysis = tri_state("是否咯血？", "hemoptysis", default="未选择")

    st.divider()
    d1, d2, d3, d4 = st.columns(4)
    with d1:
        heartburn = tri_state("是否烧心/反酸？", "heartburn", default="未选择")
        after_meal = tri_state("是否与进食相关（餐后更明显）？", "after_meal", default="未选择")
    with d2:
        relieved_by_antacid = tri_state("服用抑酸/胃药后缓解？", "relieved_by_antacid", default="未选择")
        vomiting = tri_state("是否出现明显呕吐（尤其剧烈/反复）？", "vomiting", default="未选择")
    with d3:
        worse_with_movement = tri_state("活动/姿势变化时更痛？", "worse_with_movement", default="未选择")
        panic = tri_state("是否像惊恐发作（憋闷+强烈恐惧+发抖等）？", "panic", default="未选择")
    with d4:
        stress_trigger = tri_state("是否在情绪/压力后诱发？", "stress_trigger", default="未选择")
        risk_cad = tri_state("是否存在心血管危险因素/既往心脏病史？", "risk_cad", default="未选择")

    st.divider()
    r1, r2 = st.columns(2)
    with r1:
        immobilization = tri_state("近期手术/久坐久卧/长途旅行？", "immobilization", default="未选择")
    with r2:
        leg_swelling = tri_state("是否单侧下肢肿胀/疼痛？", "leg_swelling", default="未选择")

# 实时红旗征筛查：不需要点击“生成分诊建议”也会弹窗提醒
answers_preview = ChestPainAnswers(
    pain_location=pain_location_3d or (None if pain_location_fallback == "未选择" else pain_location_fallback),
    pain_severity=pain_sev,
    sudden_onset=sudden_onset,
    pain_quality=pain_quality,
    tearing_pain=tearing_pain,
    exertional=exertional,
    relieved_by_rest=relieved_by_rest,
    after_meal=after_meal,
    relieved_by_antacid=relieved_by_antacid,
    worse_with_movement=worse_with_movement,
    reproducible=reproducible,
    sob=sob,
    radiation=radiation,  # 关键
    sweat_nausea=sweat_nausea,
    palpitations=palpitations,
    syncope=syncope,
    neuro_deficit=neuro_deficit,
    pleuritic=pleuritic,
    cough_fever=cough_fever,
    hemoptysis=hemoptysis,
    vomiting=vomiting,
    risk_cad=risk_cad,
    immobilization=immobilization,
    leg_swelling=leg_swelling,
    trauma=trauma,
    panic=panic,
    stress_trigger=stress_trigger,
    heartburn=heartburn,
)

maybe_realtime_emergency_popup(kb, answers_preview, symptom_text)

# 同时给一个“持续可见”的红色提示（避免用户关掉弹窗后忘了）
if st.session_state.get("rf_active"):
    st.error("⚠️ 系统实时检测到可能的高危信号（红旗征）。建议立即急诊评估/呼叫急救。")


# --------------------
# Run triage
# --------------------

run = st.button("🧭 生成分诊建议", type="primary")
if run:
    patient = PatientInfo(
        name=name or None,
        sex=None if sex == "未填" else sex,
        age=age,
        phone=phone or None,
    )

    # 直接复用上面已经组装好的 answers_preview（避免两套数据不一致）
    answers = answers_preview
    free_text = FreeTextInput(symptom_text=symptom_text or "")

    # --- 等待窗口：明确“正在生成中” ---
    if hasattr(st, "status"):
        with st.status("正在生成分诊建议...", expanded=True) as status:
            status.update(label="规则引擎计算中...", state="running")
            triage = triage_from_rules(kb, answers)

            top3_depts = triage.recommended_departments[:3]

            if has_key:
                status.update(label="正在抽取结构化信息（LLM）...", state="running")
                llm_extraction = extract_structured(free_text.symptom_text, answers)

                status.update(label="正在生成患者/医生摘要（LLM）...", state="running")
                patient_sum, doctor_sum = generate_summaries(
                    symptom_text=free_text.symptom_text,
                    answers=answers,
                    triage_level=triage.level,
                    dept_names=top3_depts,  # 只传 Top3
                    red_flags=[rf.name for rf in triage.red_flags],
                )
            else:
                llm_extraction = None
                patient_sum, doctor_sum = (None, None)

            status.update(label="生成完成", state="complete")
    else:
        with st.spinner("正在生成分诊建议..."):
            triage = triage_from_rules(kb, answers)
            top3_depts = triage.recommended_departments[:3]
            if has_key:
                llm_extraction = extract_structured(free_text.symptom_text, answers)
                patient_sum, doctor_sum = generate_summaries(
                    symptom_text=free_text.symptom_text,
                    answers=answers,
                    triage_level=triage.level,
                    dept_names=top3_depts,
                    red_flags=[rf.name for rf in triage.red_flags],
                )
            else:
                llm_extraction = None
                patient_sum, doctor_sum = (None, None)


    free_text = FreeTextInput(symptom_text=symptom_text or "")

    triage = triage_from_rules(kb, answers)

    # LLM extraction + summaries (optional)
    llm_extraction = extract_structured(free_text.symptom_text, answers)
    patient_sum, doctor_sum = generate_summaries(
        symptom_text=free_text.symptom_text,
        answers=answers,
        triage_level=triage.level,
        dept_names=triage.recommended_departments,
        red_flags=[rf.name for rf in triage.red_flags],
    )

    case = CaseRecord(
        patient=patient,
        answers=answers,
        free_text=free_text,
        triage=triage,
        llm_extraction=llm_extraction,
        llm_summary_for_patient=patient_sum,
        llm_summary_for_doctor=doctor_sum,
        rules_version=kb.version,
    )

    st.divider()
    st.subheader("分诊建议")

    if triage.level == "EMERGENCY":
        st.error("检测到可能的高危信号（红旗征），建议立即急诊评估/呼叫急救。")
        if triage.red_flags:
            st.write("**触发项：**")
            for rf in triage.red_flags:
                st.write(f"- {rf.name}：{rf.message}")

    level_text = {
        "EMERGENCY": "🚑 高危/需急诊",
        "URGENT": "⏱️ 建议尽快就医（24小时内）",
        "ROUTINE": "📅 可门诊就医（近期）",
    }[triage.level]
    st.markdown(f"### {level_text}")

    st.write("**推荐就诊科室（按优先级）**")
    for i, dept in enumerate(top3_depts, start=1):
        st.write(f"{i}. {dept}")

    if patient_sum:
        st.write("**给患者的说明（LLM生成）**")
        st.info(patient_sum)

    if triage.reasons:
        st.write("**规则引擎解释（可审计）**")
        for r in triage.reasons:
            st.write(f"- {r}")

    if debug:
        st.write("### 调试信息")
        st.json(case.model_dump())

    st.divider()
    st.subheader("一键导出结构化病例")
    js_bytes, pdf_bytes = export_case(case)

    st.download_button(
        label="⬇️ 下载 JSON（结构化病例）",
        data=js_bytes,
        file_name=f"case_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
    )
    st.download_button(
        label="⬇️ 下载 PDF（摘要）",
        data=pdf_bytes,
        file_name=f"case_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        mime="application/pdf",
    )

    st.caption("提示：上线前请进行临床专家审阅与验证，尤其是红旗征召回率（宁可高敏感也不要漏诊）。")

