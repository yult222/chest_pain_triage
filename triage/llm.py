from __future__ import annotations

import json
from typing import Optional

from openai import OpenAI

from .config import settings
from .schemas import ChestPainAnswers, LLMExtraction
from .utils import extract_json_object


SYSTEM_PROMPT_EXTRACT = """
你是一个医疗接诊辅助系统的“信息抽取”模块。
任务：只根据用户提供的原始文本和结构化问卷答案，抽取结构化字段并返回JSON。

严格规则：
1) 绝对不要编造任何未出现的信息。
2) 如果用户没有说/无法从答案推断出某项，输出 null 或 空数组。
3) 不要给出诊断、不要给出治疗建议、不要输出多余文本。
4) 仅输出一个JSON对象，禁止markdown代码块。
""".strip()


def _client() -> OpenAI:
    return OpenAI(api_key=settings.api_key, base_url=settings.base_url)


def extract_structured(symptom_text: str, answers: ChestPainAnswers) -> Optional[LLMExtraction]:
    if not settings.api_key:
        return None

    user_payload = {
        "symptom_text": symptom_text,
        "answers": answers.model_dump(),
        "schema": {
            "chief_complaint": "string|null",
            "hpi": "string|null",
            "key_symptoms": "string[]",
            "negated_symptoms": "string[]",
            "onset_time": "string|null",
            "risk_factors": "string[]",
            "meds": "string[]",
            "allergies": "string[]",
            "notes_for_doctor": "string|null"
        }
    }

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_EXTRACT},
        {
            "role": "user",
            "content": "请根据输入生成JSON：\n" + json.dumps(user_payload, ensure_ascii=False),
        },
    ]

    try:
        resp = _client().chat.completions.create(
            model=settings.model,
            messages=messages,
            temperature=settings.llm_temperature,
        )
        text = resp.choices[0].message.content or ""
        obj = extract_json_object(text)
        if not obj:
            return None
        return LLMExtraction.model_validate(obj)
    except Exception:
        return None


SYSTEM_PROMPT_SUMMARY = """
你是一个医疗接诊辅助系统的“总结”模块。
你的输出将用于：
- 给患者的“就诊建议说明”（非诊断、非治疗，只说明为何建议某科室/急诊，以及下一步做什么：尽快就医/呼叫急救/携带资料）。
- 给医生的“结构化接诊摘要”（尽量客观、要点式）。

严格规则：
1) 不得给出明确诊断或排除某诊断（例如“你就是心梗”）。只能使用“可能/需要排除/建议进一步评估”。
2) 不得提供药物剂量或具体治疗方案。
3) 只能引用用户输入与规则引擎产出，不得编造。
""".strip()


def generate_summaries(symptom_text: str, answers: ChestPainAnswers, triage_level: str, dept_names: list[str], red_flags: list[str]) -> tuple[Optional[str], Optional[str]]:
    if not settings.api_key:
        return (None, None)

    payload = {
        "symptom_text": symptom_text,
        "answers": answers.model_dump(),
        "triage_level": triage_level,
        "recommended_departments": dept_names,
        "red_flags": red_flags,
    }

    user_prompt = (
        "请生成两段文本，分别以 JSON 输出：\n"
        "{\"patient\": \"...\", \"doctor\": \"...\"}\n"
        "要求：patient <= 200字，doctor <= 250字；中文；不做诊断；不编造；只基于输入。\n"
        + json.dumps(payload, ensure_ascii=False)
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_SUMMARY},
        {"role": "user", "content": user_prompt},
    ]

    try:
        resp = _client().chat.completions.create(
            model=settings.model,
            messages=messages,
            temperature=0.2,
        )
        text = resp.choices[0].message.content or ""
        obj = extract_json_object(text) or {}
        return (obj.get("patient"), obj.get("doctor"))
    except Exception:
        return (None, None)
