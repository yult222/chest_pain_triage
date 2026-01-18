from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .schemas import ChestPainAnswers, RedFlagHit, TriageResult


@dataclass
class KnowledgeBase:
    version: str
    rules: Dict[str, Any]


def load_knowledge_base(path: str) -> KnowledgeBase:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    version = str(data.get("version", "0"))
    return KnowledgeBase(version=version, rules=data)


def _get_field(answers: Dict[str, Any], field: str) -> Any:
    return answers.get(field)


def eval_expr(expr: Any, answers: Dict[str, Any]) -> bool:
    """Evaluate a small, safe boolean DSL.

    Supported forms:
    - {"all": [expr, ...]}
    - {"any": [expr, ...]}
    - {"field": "name", "eq": value}
    - {"field": "name", "in": [v1, v2]}
    - {"field": "name", "gte": number}
    - {"field": "name", "lte": number}

    Any unknown operator returns False.
    """
    if expr is None:
        return False

    if isinstance(expr, dict):
        if "all" in expr:
            return all(eval_expr(e, answers) for e in expr.get("all", []))
        if "any" in expr:
            return any(eval_expr(e, answers) for e in expr.get("any", []))

        field = expr.get("field")
        if field:
            val = _get_field(answers, field)
            if "eq" in expr:
                return val == expr.get("eq")
            if "in" in expr:
                return val in (expr.get("in") or [])
            if "gte" in expr:
                try:
                    return float(val) >= float(expr.get("gte"))
                except Exception:
                    return False
            if "lte" in expr:
                try:
                    return float(val) <= float(expr.get("lte"))
                except Exception:
                    return False

    return False


def evaluate_red_flags(kb: KnowledgeBase, answers: ChestPainAnswers) -> List[RedFlagHit]:
    a = answers.model_dump()
    hits: List[RedFlagHit] = []
    for rule in kb.rules.get("red_flags", []):
        expr = rule.get("expr")
        if eval_expr(expr, a):
            hits.append(
                RedFlagHit(
                    id=str(rule.get("id")),
                    name=str(rule.get("name")),
                    message=str(rule.get("message")),
                )
            )
    return hits


def compute_scores(kb: KnowledgeBase, answers: ChestPainAnswers) -> Dict[str, float]:
    a = answers.model_dump()
    scores: Dict[str, float] = {"cardiac": 0, "pulmonary": 0, "gi": 0, "msk": 0, "psych": 0}

    for rule in kb.rules.get("score_rules", []):
        when = rule.get("when")
        add = rule.get("add") or {}
        if eval_expr(when, a):
            for k, v in add.items():
                if k not in scores:
                    scores[k] = 0
                scores[k] += float(v)

    return scores


def rank_departments(kb: KnowledgeBase, scores: Dict[str, float]) -> List[Tuple[str, float]]:
    mapping: Dict[str, str] = kb.rules.get("dept_mapping", {})
    dept_scores: Dict[str, float] = {}

    for system_key, score in scores.items():
        dept_key = mapping.get(system_key)
        if not dept_key:
            continue
        dept_scores[dept_key] = dept_scores.get(dept_key, 0) + float(score)

    ranked = sorted(dept_scores.items(), key=lambda x: x[1], reverse=True)
    return ranked


def triage_from_rules(kb: KnowledgeBase, answers: ChestPainAnswers) -> TriageResult:
    red_flags = evaluate_red_flags(kb, answers)
    scores = compute_scores(kb, answers)

    overall = sum(scores.values())
    thresholds = kb.rules.get("triage_thresholds", {})
    urgent_th = float(thresholds.get("urgent_overall", 6))

    if red_flags:
        level = "EMERGENCY"
    elif overall >= urgent_th:
        level = "URGENT"
    else:
        level = "ROUTINE"

    ranked = rank_departments(kb, scores)
    departments_meta = kb.rules.get("departments", {})

    # Always include emergency as fallback in list (but top when EMERGENCY)
    dept_list: List[str] = []
    if level == "EMERGENCY":
        dept_list.append("emergency")

    for dept_key, _ in ranked:
        if dept_key not in dept_list:
            dept_list.append(dept_key)

    # Fallbacks
    if not dept_list:
        dept_list = ["general"]
        # Cap recommendation list length (Top-3)
        MAX_RECS = 3
        dept_list = dept_list[:MAX_RECS]

    # Build details
    details: Dict[str, Dict[str, Any]] = {}
    for dept_key in dept_list:
        meta = departments_meta.get(dept_key, {})
        details[dept_key] = {
            "name": meta.get("name", dept_key),
            "hint": meta.get("hint", ""),
            "score": float(next((s for k, s in ranked if k == dept_key), 0.0)),
        }

    reasons: List[str] = []
    # Simple reason generation (transparent)
    top_systems = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    for sys_key, score in top_systems[:2]:
        if score <= 0:
            continue
        reasons.append(f"{sys_key} 相关特征得分较高（{score:.0f}）。")
    if red_flags:
        reasons.extend([f"触发红旗征：{rf.name}" for rf in red_flags])

    recommended = [details[k]["name"] for k in dept_list]

    return TriageResult(
        level=level,  # type: ignore[arg-type]
        recommended_departments=recommended,
        department_details=details,
        red_flags=red_flags,
        score_breakdown=scores,
        reasons=reasons,
    )
