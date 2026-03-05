from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .schemas import ChestPainAnswers, EvidenceContribution, RedFlagHit, TriageResult

try:
    import yaml
except Exception:  # pragma: no cover - optional dependency import guard
    yaml = None


EPS_PRIOR = 1e-6
MAX_ABS_LOG_ODDS = 12.0
MISSING_SENTINELS = {"", "未选择"}
ALLOWED_OPERATORS = {"eq", "in", "gte", "lte"}
ALLOWED_MISSING_POLICIES = {"ask", "assume_unknown", "conservative_upgrade"}


class RuleValidationError(ValueError):
    def __init__(self, message: str, rule_path: str) -> None:
        super().__init__(message)
        self.rule_path = rule_path


@dataclass
class KnowledgeBase:
    version: str
    rules: Dict[str, Any]
    source_path: str = ""

    @property
    def engine_mode(self) -> str:
        return _detect_engine_mode(self.version, self.rules)

    @property
    def profile_ids(self) -> List[str]:
        if self.engine_mode != "v2":
            return []
        profiles = self.rules.get("profiles") or {}
        if not isinstance(profiles, dict):
            return []
        return [str(k) for k in profiles.keys()]

    @property
    def default_profile(self) -> Optional[str]:
        if self.engine_mode != "v2":
            return None
        explicit = self.rules.get("default_profile")
        if isinstance(explicit, str) and explicit in self.profile_ids:
            return explicit
        profile_ids = self.profile_ids
        return profile_ids[0] if profile_ids else None


def _detect_engine_mode(version: str, rules: Dict[str, Any]) -> str:
    if str(version).startswith("0.2"):
        return "v2"
    if "profiles" in rules and "evidence_rules" in rules:
        return "v2"
    return "v1"


def load_knowledge_base(path: str) -> KnowledgeBase:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"规则文件不存在：{p}")

    data = _read_rules_file(p)
    if not isinstance(data, dict):
        raise ValueError(f"规则文件格式错误：根节点必须为对象，file={p}")

    version = str(data.get("version", "0")).strip()
    kb = KnowledgeBase(version=version, rules=data, source_path=str(p))

    try:
        validate_knowledge_base(kb)
    except RuleValidationError as exc:
        raise ValueError(
            f"规则文件加载失败: file={p}, version={version}, error_at={exc.rule_path}, detail={exc}"
        ) from exc

    return kb


def _read_rules_file(path: Path) -> Dict[str, Any]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")

    if suffix in {".yaml", ".yml"}:
        if yaml is None:
            raise ValueError("读取 YAML 规则文件需要 PyYAML，请先安装：pip install pyyaml")
        obj = yaml.safe_load(text)  # type: ignore[union-attr]
        if obj is None:
            return {}
        if not isinstance(obj, dict):
            raise ValueError("YAML 根节点必须是对象")
        return obj

    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError("JSON 根节点必须是对象")
    return obj


def validate_knowledge_base(kb: KnowledgeBase) -> None:
    if kb.engine_mode == "v2":
        _validate_v2_rules(kb.rules)


def _raise_validation(rule_path: str, message: str) -> None:
    raise RuleValidationError(message, rule_path)


def _to_positive_float(value: Any, rule_path: str, what: str) -> float:
    try:
        v = float(value)
    except Exception as exc:
        _raise_validation(rule_path, f"{what} 必须是数值")
        raise exc  # pragma: no cover
    if v <= 0:
        _raise_validation(rule_path, f"{what} 必须 > 0")
    return v


def _to_probability(value: Any, rule_path: str, what: str, allow_zero: bool = True) -> float:
    try:
        v = float(value)
    except Exception as exc:
        _raise_validation(rule_path, f"{what} 必须是数值")
        raise exc  # pragma: no cover
    if allow_zero:
        ok = 0.0 <= v <= 1.0
    else:
        ok = 0.0 < v < 1.0
    if not ok:
        _raise_validation(rule_path, f"{what} 必须在 [0,1] 范围内")
    return v


def _validate_leaf_operator(expr: Dict[str, Any], rule_path: str) -> None:
    if "op" in expr:
        op = str(expr.get("op"))
        if op not in ALLOWED_OPERATORS:
            _raise_validation(rule_path, f"不支持的操作符：{op}")
        if op == "in":
            values = expr.get("values")
            if not isinstance(values, list):
                _raise_validation(rule_path, "op=in 时必须提供 values 数组")
        else:
            if "value" not in expr:
                _raise_validation(rule_path, f"op={op} 时必须提供 value")
        return

    legacy_ops = [k for k in ("eq", "in", "gte", "lte") if k in expr]
    if len(legacy_ops) != 1:
        _raise_validation(rule_path, "叶子表达式必须包含一个比较操作（eq/in/gte/lte）")
    if legacy_ops[0] == "in" and not isinstance(expr.get("in"), list):
        _raise_validation(rule_path, "in 操作必须是数组")


def _validate_expr(expr: Any, rule_path: str, known_fields: set[str], known_concepts: set[str]) -> None:
    if not isinstance(expr, dict):
        _raise_validation(rule_path, "表达式必须是对象")

    for group_key in ("all_of", "all", "any_of", "any"):
        if group_key in expr:
            items = expr.get(group_key)
            if not isinstance(items, list) or not items:
                _raise_validation(rule_path, f"{group_key} 必须是非空数组")
            for idx, item in enumerate(items):
                _validate_expr(item, f"{rule_path}.{group_key}[{idx}]", known_fields, known_concepts)
            return

    if "field" in expr:
        field = expr.get("field")
        if not isinstance(field, str) or field not in known_fields:
            _raise_validation(rule_path, f"未知字段：{field}")
        _validate_leaf_operator(expr, rule_path)
        return

    if "concept" in expr:
        concept = expr.get("concept")
        if not isinstance(concept, str) or concept not in known_concepts:
            _raise_validation(rule_path, f"未知 concept：{concept}")
        _validate_leaf_operator(expr, rule_path)
        return

    _raise_validation(rule_path, "表达式必须包含 all_of/any_of 或 field/concept")


def _validate_v2_rules(rules: Dict[str, Any]) -> None:
    known_fields = set(ChestPainAnswers.model_fields.keys())

    strength_scale = rules.get("strength_scale")
    if not isinstance(strength_scale, dict) or not strength_scale:
        _raise_validation("strength_scale", "必须提供非空 strength_scale")
    for name, cfg in strength_scale.items():
        rule_path = f"strength_scale.{name}"
        if not isinstance(cfg, dict):
            _raise_validation(rule_path, "强度项必须是对象")
        _to_positive_float(cfg.get("lr"), f"{rule_path}.lr", "lr")

    profiles = rules.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        _raise_validation("profiles", "必须提供至少一个 profile")

    default_profile = rules.get("default_profile")
    if default_profile is not None and default_profile not in profiles:
        _raise_validation("default_profile", "default_profile 必须存在于 profiles")

    all_hypotheses: set[str] = set()
    for profile_id, profile in profiles.items():
        profile_path = f"profiles.{profile_id}"
        if not isinstance(profile, dict):
            _raise_validation(profile_path, "profile 必须是对象")

        priors = profile.get("priors")
        if not isinstance(priors, dict) or not priors:
            _raise_validation(f"{profile_path}.priors", "必须提供非空 priors")

        for h, p in priors.items():
            _to_probability(p, f"{profile_path}.priors.{h}", "先验概率", allow_zero=False)
            all_hypotheses.add(str(h))

        decision_thresholds = profile.get("decision_thresholds") or {}
        if not isinstance(decision_thresholds, dict):
            _raise_validation(f"{profile_path}.decision_thresholds", "decision_thresholds 必须是对象")
        for lv in ("emergency", "urgent"):
            if lv not in decision_thresholds:
                continue
            block = decision_thresholds.get(lv)
            if not isinstance(block, dict):
                _raise_validation(f"{profile_path}.decision_thresholds.{lv}", "阈值块必须是对象")
            if "any_red_flag" in block and not isinstance(block.get("any_red_flag"), bool):
                _raise_validation(f"{profile_path}.decision_thresholds.{lv}.any_red_flag", "必须是布尔值")
            if "any_posterior_ge" in block:
                _to_probability(
                    block.get("any_posterior_ge"),
                    f"{profile_path}.decision_thresholds.{lv}.any_posterior_ge",
                    "阈值",
                )

        danger_hypotheses = profile.get("danger_hypotheses") or []
        if not isinstance(danger_hypotheses, list):
            _raise_validation(f"{profile_path}.danger_hypotheses", "danger_hypotheses 必须是数组")
        prior_keys = set(priors.keys())
        for idx, h in enumerate(danger_hypotheses):
            if h not in prior_keys:
                _raise_validation(
                    f"{profile_path}.danger_hypotheses[{idx}]",
                    f"高危病因必须出现在 priors 中：{h}",
                )

    concepts = rules.get("concepts") or {}
    if not isinstance(concepts, dict):
        _raise_validation("concepts", "concepts 必须是对象")
    known_concepts = {str(k) for k in concepts.keys()}
    for concept_name, cfg in concepts.items():
        concept_path = f"concepts.{concept_name}"
        if not isinstance(cfg, dict):
            _raise_validation(concept_path, "concept 必须是对象")
        if "when" not in cfg:
            _raise_validation(concept_path, "concept 必须包含 when")
        _validate_expr(cfg.get("when"), f"{concept_path}.when", known_fields, known_concepts)

    red_flags = rules.get("red_flags") or []
    if not isinstance(red_flags, list):
        _raise_validation("red_flags", "red_flags 必须是数组")
    for idx, rule in enumerate(red_flags):
        base = f"red_flags[{idx}]"
        if not isinstance(rule, dict):
            _raise_validation(base, "red_flag 必须是对象")
        for key in ("id", "name", "message"):
            if not str(rule.get(key, "")).strip():
                _raise_validation(f"{base}.{key}", f"{key} 不能为空")
        when = rule.get("when") if "when" in rule else rule.get("expr")
        if when is None:
            _raise_validation(f"{base}.when", "red_flag 必须包含 when/expr")
        _validate_expr(when, f"{base}.when", known_fields, known_concepts)

    evidence_rules = rules.get("evidence_rules") or []
    if not isinstance(evidence_rules, list) or not evidence_rules:
        _raise_validation("evidence_rules", "必须提供非空 evidence_rules")
    for idx, rule in enumerate(evidence_rules):
        base = f"evidence_rules[{idx}]"
        if not isinstance(rule, dict):
            _raise_validation(base, "证据规则必须是对象")
        if not str(rule.get("id", "")).strip():
            _raise_validation(f"{base}.id", "id 不能为空")
        when = rule.get("when")
        if when is None:
            _raise_validation(f"{base}.when", "证据规则必须包含 when")
        _validate_expr(when, f"{base}.when", known_fields, known_concepts)

        affects = rule.get("affects")
        if not isinstance(affects, dict) or not affects:
            _raise_validation(f"{base}.affects", "affects 必须是非空对象")
        for hypothesis, impact in affects.items():
            impact_path = f"{base}.affects.{hypothesis}"
            if hypothesis not in all_hypotheses:
                _raise_validation(impact_path, "病因必须在 profiles.*.priors 中定义")
            if not isinstance(impact, dict):
                _raise_validation(impact_path, "affect 配置必须是对象")

            direction = str(impact.get("direction", "support"))
            if direction not in {"support", "oppose"}:
                _raise_validation(f"{impact_path}.direction", "direction 必须是 support 或 oppose")

            if "strength" in impact:
                strength = impact.get("strength")
                if strength not in strength_scale:
                    _raise_validation(
                        f"{impact_path}.strength",
                        "strength 必须引用 strength_scale 已定义的档位",
                    )
            elif "lr" in impact:
                _to_positive_float(impact.get("lr"), f"{impact_path}.lr", "lr")
            else:
                _raise_validation(impact_path, "必须提供 strength 或 lr")

    missingness_policy = rules.get("missingness_policy") or {}
    if not isinstance(missingness_policy, dict):
        _raise_validation("missingness_policy", "missingness_policy 必须是对象")
    critical_questions = missingness_policy.get("critical_questions") or []
    if not isinstance(critical_questions, list):
        _raise_validation("missingness_policy.critical_questions", "critical_questions 必须是数组")
    for idx, item in enumerate(critical_questions):
        base = f"missingness_policy.critical_questions[{idx}]"
        if not isinstance(item, dict):
            _raise_validation(base, "critical_questions 项必须是对象")
        field = item.get("field")
        if not isinstance(field, str) or field not in known_fields:
            _raise_validation(f"{base}.field", "field 必须是已存在问卷字段")
        applies_to = item.get("applies_to") or []
        if not isinstance(applies_to, list):
            _raise_validation(f"{base}.applies_to", "applies_to 必须是数组")
        for j, hypothesis in enumerate(applies_to):
            if hypothesis not in all_hypotheses:
                _raise_validation(f"{base}.applies_to[{j}]", "applies_to 必须引用已定义病因")
        if_missing = str(item.get("if_missing", "ask"))
        if if_missing not in ALLOWED_MISSING_POLICIES:
            _raise_validation(
                f"{base}.if_missing",
                f"if_missing 必须是 {', '.join(sorted(ALLOWED_MISSING_POLICIES))}",
            )

    output_mapping = rules.get("output_mapping")
    if not isinstance(output_mapping, dict):
        _raise_validation("output_mapping", "必须提供 output_mapping")
    hypothesis_to_department = output_mapping.get("hypothesis_to_department")
    if not isinstance(hypothesis_to_department, dict) or not hypothesis_to_department:
        _raise_validation("output_mapping.hypothesis_to_department", "必须提供病因到科室映射")
    for hypothesis in all_hypotheses:
        if hypothesis not in hypothesis_to_department:
            _raise_validation(
                "output_mapping.hypothesis_to_department",
                f"缺少病因映射：{hypothesis}",
            )

    department_meta = output_mapping.get("department_meta") or {}
    if not isinstance(department_meta, dict):
        _raise_validation("output_mapping.department_meta", "department_meta 必须是对象")


def _get_field(answers: Dict[str, Any], field: str) -> Any:
    return answers.get(field)


def _compare(op: str, val: Any, expected: Any) -> bool:
    if op == "eq":
        return val == expected
    if op == "in":
        return val in (expected or [])
    if op == "gte":
        try:
            return float(val) >= float(expected)
        except Exception:
            return False
    if op == "lte":
        try:
            return float(val) <= float(expected)
        except Exception:
            return False
    return False


def _eval_expr(
    expr: Any,
    answers: Dict[str, Any],
    concept_resolver: Optional[Callable[[str], bool]] = None,
) -> bool:
    if expr is None or not isinstance(expr, dict):
        return False

    if "all_of" in expr:
        return all(_eval_expr(e, answers, concept_resolver) for e in expr.get("all_of", []))
    if "all" in expr:
        return all(_eval_expr(e, answers, concept_resolver) for e in expr.get("all", []))
    if "any_of" in expr:
        return any(_eval_expr(e, answers, concept_resolver) for e in expr.get("any_of", []))
    if "any" in expr:
        return any(_eval_expr(e, answers, concept_resolver) for e in expr.get("any", []))

    target_val: Any = None
    if "field" in expr:
        field = expr.get("field")
        if not isinstance(field, str):
            return False
        target_val = _get_field(answers, field)
    elif "concept" in expr:
        concept = expr.get("concept")
        if not isinstance(concept, str) or concept_resolver is None:
            return False
        target_val = concept_resolver(concept)
    else:
        return False

    if "op" in expr:
        op = str(expr.get("op"))
        if op == "in":
            return _compare("in", target_val, expr.get("values"))
        return _compare(op, target_val, expr.get("value"))

    if "eq" in expr:
        return _compare("eq", target_val, expr.get("eq"))
    if "in" in expr:
        return _compare("in", target_val, expr.get("in"))
    if "gte" in expr:
        return _compare("gte", target_val, expr.get("gte"))
    if "lte" in expr:
        return _compare("lte", target_val, expr.get("lte"))
    return False


def eval_expr(expr: Any, answers: Dict[str, Any]) -> bool:
    """Public compatibility wrapper for expression evaluation."""
    return _eval_expr(expr, answers, concept_resolver=None)


def _build_concept_resolver(
    concepts: Dict[str, Any], answers: Dict[str, Any]
) -> Tuple[Callable[[str], bool], Dict[str, bool]]:
    memo: Dict[str, bool] = {}
    visiting: List[str] = []

    def resolve(concept_name: str) -> bool:
        if concept_name in memo:
            return memo[concept_name]
        if concept_name in visiting:
            cycle = " -> ".join([*visiting, concept_name])
            raise ValueError(f"concept 依赖存在循环：{cycle}")

        concept = concepts.get(concept_name)
        if not isinstance(concept, dict):
            raise ValueError(f"concept 不存在或格式错误：{concept_name}")

        visiting.append(concept_name)
        try:
            when = concept.get("when")
            value = bool(_eval_expr(when, answers, concept_resolver=resolve))
            memo[concept_name] = value
            return value
        finally:
            visiting.pop()

    return resolve, memo


def _is_missing_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() in MISSING_SENTINELS
    return False


def _safe_clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _clamp_prior(prior: float) -> float:
    return _safe_clamp(prior, EPS_PRIOR, 1.0 - EPS_PRIOR)


def _sigmoid(x: float) -> float:
    x = _safe_clamp(x, -MAX_ABS_LOG_ODDS, MAX_ABS_LOG_ODDS)
    return 1.0 / (1.0 + math.exp(-x))


def _resolve_profile_id(kb: KnowledgeBase, profile_id: Optional[str]) -> str:
    profile_ids = kb.profile_ids
    if not profile_ids:
        raise ValueError("v0.2 规则缺少 profiles")
    if profile_id:
        if profile_id not in profile_ids:
            raise ValueError(f"未知 profile：{profile_id}，可选：{', '.join(profile_ids)}")
        return profile_id
    return kb.default_profile or profile_ids[0]


def _resolve_lr(impact: Dict[str, Any], strength_scale: Dict[str, Any]) -> float:
    if "lr" in impact:
        return max(float(impact.get("lr", 1.0)), EPS_PRIOR)
    strength = impact.get("strength")
    cfg = strength_scale.get(strength) if isinstance(strength_scale, dict) else None
    if isinstance(cfg, dict) and "lr" in cfg:
        return max(float(cfg.get("lr", 1.0)), EPS_PRIOR)
    return 1.0


def _evaluate_red_flags_v1(kb: KnowledgeBase, answers_dict: Dict[str, Any]) -> List[RedFlagHit]:
    hits: List[RedFlagHit] = []
    for rule in kb.rules.get("red_flags", []):
        expr = rule.get("expr")
        if _eval_expr(expr, answers_dict):
            hits.append(
                RedFlagHit(
                    id=str(rule.get("id", "")),
                    name=str(rule.get("name", "")),
                    message=str(rule.get("message", "")),
                )
            )
    return hits


def _evaluate_red_flags_v2(
    rules: Dict[str, Any],
    answers_dict: Dict[str, Any],
    concept_resolver: Callable[[str], bool],
) -> List[RedFlagHit]:
    hits: List[RedFlagHit] = []
    for rule in rules.get("red_flags", []):
        when = rule.get("when") if "when" in rule else rule.get("expr")
        if _eval_expr(when, answers_dict, concept_resolver):
            hits.append(
                RedFlagHit(
                    id=str(rule.get("id", "")),
                    name=str(rule.get("name", "")),
                    message=str(rule.get("message", "")),
                )
            )
    return hits


def _collect_missing_critical_questions(
    rules: Dict[str, Any],
    answers_dict: Dict[str, Any],
    danger_hypotheses: List[str],
) -> List[str]:
    policy = rules.get("missingness_policy") or {}
    questions = policy.get("critical_questions") or []
    if not isinstance(questions, list):
        return []

    danger_set = set(danger_hypotheses)
    missing_fields: List[str] = []
    for item in questions:
        if not isinstance(item, dict):
            continue
        field = item.get("field")
        if not isinstance(field, str):
            continue

        applies_to = item.get("applies_to") or []
        if isinstance(applies_to, list) and applies_to:
            if danger_set and danger_set.isdisjoint(set(applies_to)):
                continue

        if_missing = str(item.get("if_missing", "ask"))
        if if_missing not in ALLOWED_MISSING_POLICIES:
            continue
        if if_missing not in {"ask", "conservative_upgrade"}:
            continue

        if _is_missing_value(answers_dict.get(field)):
            missing_fields.append(field)

    # stable de-duplication
    return list(dict.fromkeys(missing_fields).keys())


def evaluate_red_flags(kb: KnowledgeBase, answers: ChestPainAnswers) -> List[RedFlagHit]:
    a = answers.model_dump()
    if kb.engine_mode == "v2":
        concepts = kb.rules.get("concepts") or {}
        concept_resolver, _ = _build_concept_resolver(concepts, a)
        return _evaluate_red_flags_v2(kb.rules, a, concept_resolver)
    return _evaluate_red_flags_v1(kb, a)


def compute_scores(kb: KnowledgeBase, answers: ChestPainAnswers) -> Dict[str, float]:
    if kb.engine_mode != "v1":
        return {}

    a = answers.model_dump()
    scores: Dict[str, float] = {"cardiac": 0, "pulmonary": 0, "gi": 0, "msk": 0, "psych": 0}
    for rule in kb.rules.get("score_rules", []):
        when = rule.get("when")
        add = rule.get("add") or {}
        if _eval_expr(when, a):
            for key, val in add.items():
                scores[key] = scores.get(key, 0.0) + float(val)
    return scores


def rank_departments(kb: KnowledgeBase, scores: Dict[str, float]) -> List[Tuple[str, float]]:
    mapping: Dict[str, str] = kb.rules.get("dept_mapping", {})
    dept_scores: Dict[str, float] = {}
    for system_key, score in scores.items():
        dept_key = mapping.get(system_key)
        if not dept_key:
            continue
        dept_scores[dept_key] = dept_scores.get(dept_key, 0.0) + float(score)
    return sorted(dept_scores.items(), key=lambda x: x[1], reverse=True)


def _triage_v1_score_engine(kb: KnowledgeBase, answers: ChestPainAnswers) -> TriageResult:
    red_flags = _evaluate_red_flags_v1(kb, answers.model_dump())
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

    dept_list: List[str] = []
    if level == "EMERGENCY":
        dept_list.append("emergency")
    for dept_key, _ in ranked:
        if dept_key not in dept_list:
            dept_list.append(dept_key)
    if not dept_list:
        dept_list = ["general"]

    details: Dict[str, Dict[str, Any]] = {}
    for dept_key in dept_list:
        meta = departments_meta.get(dept_key, {})
        details[dept_key] = {
            "name": meta.get("name", dept_key),
            "hint": meta.get("hint", ""),
            "score": float(next((s for k, s in ranked if k == dept_key), 0.0)),
        }

    reasons: List[str] = []
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
        engine_mode="v1",
        profile_id=None,
        recommended_departments=recommended,
        department_details=details,
        red_flags=red_flags,
        score_breakdown=scores,
        reasons=reasons,
    )


def _triage_v2_prior_evidence_engine(
    kb: KnowledgeBase,
    answers: ChestPainAnswers,
    profile_id: Optional[str],
) -> TriageResult:
    rules = kb.rules
    a = answers.model_dump()

    chosen_profile = _resolve_profile_id(kb, profile_id)
    profiles = rules.get("profiles") or {}
    profile = profiles.get(chosen_profile) or {}
    priors_input = profile.get("priors") or {}

    prior_breakdown: Dict[str, float] = {}
    log_odds: Dict[str, float] = {}
    for hypothesis, p in priors_input.items():
        prior = _clamp_prior(float(p))
        prior_breakdown[str(hypothesis)] = prior
        log_odds[str(hypothesis)] = math.log(prior / (1.0 - prior))

    concepts = rules.get("concepts") or {}
    concept_resolver, _ = _build_concept_resolver(concepts, a)
    red_flags = _evaluate_red_flags_v2(rules, a, concept_resolver)

    strength_scale = rules.get("strength_scale") or {}
    evidence_contrib_all: List[EvidenceContribution] = []
    for rule in rules.get("evidence_rules", []):
        rule_id = str(rule.get("id", ""))
        matched = _eval_expr(rule.get("when"), a, concept_resolver=concept_resolver)
        affects = rule.get("affects") or {}
        for hypothesis, impact in affects.items():
            if not isinstance(impact, dict):
                continue
            hypothesis = str(hypothesis)
            if hypothesis not in log_odds:
                prior_breakdown[hypothesis] = EPS_PRIOR
                log_odds[hypothesis] = math.log(EPS_PRIOR / (1.0 - EPS_PRIOR))

            direction = str(impact.get("direction", "support"))
            direction = "oppose" if direction == "oppose" else "support"
            base_lr = _resolve_lr(impact, strength_scale)
            lr_effective = (1.0 / base_lr) if direction == "oppose" else base_lr
            log_lr = math.log(max(lr_effective, EPS_PRIOR))

            if matched:
                log_odds[hypothesis] = _safe_clamp(
                    log_odds[hypothesis] + log_lr,
                    -MAX_ABS_LOG_ODDS,
                    MAX_ABS_LOG_ODDS,
                )

            evidence_contrib_all.append(
                EvidenceContribution(
                    rule_id=rule_id,
                    hypothesis=hypothesis,
                    direction=direction,  # type: ignore[arg-type]
                    lr=float(lr_effective),
                    log_lr=float(log_lr),
                    matched=bool(matched),
                )
            )

    posterior_breakdown = {h: _sigmoid(v) for h, v in log_odds.items()}

    decision_thresholds = profile.get("decision_thresholds") or {}
    emergency_cfg = decision_thresholds.get("emergency") or {}
    urgent_cfg = decision_thresholds.get("urgent") or {}

    danger_hypotheses = profile.get("danger_hypotheses") or list(prior_breakdown.keys())
    if not isinstance(danger_hypotheses, list):
        danger_hypotheses = list(prior_breakdown.keys())
    danger_hypotheses = [str(h) for h in danger_hypotheses]

    emergency_any_red_flag = bool(emergency_cfg.get("any_red_flag", True))
    emergency_posterior_threshold = emergency_cfg.get("any_posterior_ge")
    urgent_posterior_threshold = urgent_cfg.get("any_posterior_ge")

    level = "ROUTINE"
    if emergency_any_red_flag and red_flags:
        level = "EMERGENCY"
    else:
        if emergency_posterior_threshold is not None:
            th = float(emergency_posterior_threshold)
            if any(posterior_breakdown.get(h, 0.0) >= th for h in danger_hypotheses):
                level = "EMERGENCY"

        if level != "EMERGENCY" and urgent_posterior_threshold is not None:
            th = float(urgent_posterior_threshold)
            if any(posterior_breakdown.get(h, 0.0) >= th for h in danger_hypotheses):
                level = "URGENT"

    missing_critical_questions = _collect_missing_critical_questions(rules, a, danger_hypotheses)
    if missing_critical_questions and level == "ROUTINE":
        level = "URGENT"

    output_mapping = rules.get("output_mapping") or {}
    hypothesis_to_department = output_mapping.get("hypothesis_to_department") or {}
    departments_meta = output_mapping.get("department_meta") or {}

    dept_scores: Dict[str, float] = {}
    for hypothesis, posterior in posterior_breakdown.items():
        dept_key = hypothesis_to_department.get(hypothesis)
        if not dept_key:
            continue
        dept_scores[dept_key] = dept_scores.get(dept_key, 0.0) + float(posterior)
    ranked_depts = sorted(dept_scores.items(), key=lambda x: x[1], reverse=True)

    dept_list: List[str] = []
    if level == "EMERGENCY":
        dept_list.append("emergency")
    for dept_key, _ in ranked_depts:
        if dept_key not in dept_list:
            dept_list.append(dept_key)
    if not dept_list:
        dept_list = ["general"]

    details: Dict[str, Dict[str, Any]] = {}
    for dept_key in dept_list:
        meta = departments_meta.get(dept_key, {})
        details[dept_key] = {
            "name": meta.get("name", dept_key),
            "hint": meta.get("hint", ""),
            "score": float(dept_scores.get(dept_key, 0.0)),
        }

    recommended = [details[k]["name"] for k in dept_list]

    evidence_top = sorted(
        [e for e in evidence_contrib_all if e.matched],
        key=lambda e: abs(e.log_lr),
        reverse=True,
    )[:8]

    reasons: List[str] = [f"使用规则 profile：{chosen_profile}"]
    if red_flags:
        reasons.extend([f"触发红旗征：{rf.name}" for rf in red_flags[:3]])
    top_danger = sorted(
        ((h, posterior_breakdown.get(h, 0.0)) for h in danger_hypotheses),
        key=lambda x: x[1],
        reverse=True,
    )[:3]
    for hypothesis, posterior in top_danger:
        reasons.append(f"{hypothesis} 后验概率={posterior:.3f}")
    for ev in evidence_top[:3]:
        reasons.append(
            f"证据 {ev.rule_id} -> {ev.hypothesis} ({ev.direction}, LR={ev.lr:.2f}, logLR={ev.log_lr:+.3f})"
        )
    if missing_critical_questions:
        reasons.append(f"关键问题未回答：{', '.join(missing_critical_questions)}（已保守升级）")

    return TriageResult(
        level=level,  # type: ignore[arg-type]
        engine_mode="v2",
        profile_id=chosen_profile,
        recommended_departments=recommended,
        department_details=details,
        red_flags=red_flags,
        score_breakdown={},
        prior_breakdown=prior_breakdown,
        posterior_breakdown=posterior_breakdown,
        evidence_top=evidence_top,
        missing_critical_questions=missing_critical_questions,
        reasons=reasons,
    )


def triage_from_rules(
    kb: KnowledgeBase,
    answers: ChestPainAnswers,
    profile_id: Optional[str] = None,
) -> TriageResult:
    if kb.engine_mode == "v2":
        return _triage_v2_prior_evidence_engine(kb, answers, profile_id=profile_id)
    return _triage_v1_score_engine(kb, answers)
