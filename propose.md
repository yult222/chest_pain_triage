# 医生可写规则引擎模式：先验-证据（Prior + Evidence, Log-odds / LR）规则本

这一模式的核心是：医生主要写“先验（某人群/场景下各病因的基础概率）”与“证据强度（某体征/症状对某病因的支持/反对力度）”，而不是写无单位的加分与混合总分阈值。引擎内部用可加的 log-odds（或 log LR）做推断，并把“紧急度决策”和“病因/科室倾向”解耦。

---

## 1. 设计目标（面向医生的可写性）
1) 医生输入的对象要“有语义单位”：先验概率、似然比强弱、红旗征触发，而不是任意加分。
2) 同一份规则本应当支持不同场景（急诊/门诊/体检中心）→ 用 profile 管理“先验 + 阈值”。
3) 规则书写尽量接近临床表述：先定义可复用的“临床概念（concept）”，再引用 concept 写红旗征与证据条目。
4) 缺失值要显式处理：对高危问题，缺失不是“否”，而是 Unknown（需要补问/保守升级）。

---

## 2. 核心语义（引擎的数学含义）
对每个候选病因/假设 `h`（如 ACS/PE/PTX/GERD/MSK/Panic 等）：

- 先验：`prior[h] = P(h)`（由 profile 给出）
- 证据：每条证据规则提供一个 `LR`（似然比）或强度档位（弱/中/强）映射到 LR
- 后验（以 odds 形式累乘）：
  - `Odds(h|x) = Odds(h) * ∏ LR_i(h)`
  - 取对数后可加：`logOdds(h|x) = logOdds(h) + Σ logLR_i(h)`

紧急度与科室推荐分开做：
- 紧急度：只由“高危病因集合”的后验概率或硬触发红旗征决定
- 科室倾向：按各病因后验或证据强度排序，再映射到科室

---

## 3. 面向医生的配置结构（YAML/JSON 均可；此处用 YAML 表达更易读）

```yaml
version: "0.2"

# 3.1 证据强度档位（医生通常不改，只选 weak/moderate/strong）
strength_scale:
  weak:     { lr: 1.5 }   # logLR≈0.405
  moderate: { lr: 2.2 }   # logLR≈0.788
  strong:   { lr: 4.0 }   # logLR≈1.386
  # oppose 表示反向证据：lr 会在内部取倒数（1/lr）

# 3.2 profiles：医生写“不同场景/人群的先验与阈值”
profiles:
  outpatient_adult:
    priors:
      ACS: 0.03
      PE:  0.01
      PTX: 0.005
      DISSECTION: 0.001
      GERD: 0.10
      MSK:  0.20
      PANIC: 0.05

    decision_thresholds:
      emergency:
        any_red_flag: true
        # 或：高危病因任一后验 >= 0.20 也可视为需急诊（可选）
        any_posterior_ge: 0.20
      urgent:
        any_posterior_ge: 0.05

    danger_hypotheses: [ACS, PE, PTX, DISSECTION, BOERHAAVE]

# 3.3 临床概念（concept）：先把“临床语言”固化成可复用的布尔/数值概念
# 医生写 concept 时只需用少量 AND/OR；UI 可以图形化生成。
concepts:
  ischemic_like_pain:
    type: boolean
    when:
      all_of:
        - field: pain_quality
          op: in
          values: ["压榨/紧缩", "压迫感/沉重感"]
        - any_of:
            - { field: exertional, op: eq, value: "是" }
            - { field: radiation,  op: eq, value: "是" }
            - { field: sweat_nausea, op: eq, value: "是" }

  pleuritic_pain:
    type: boolean
    when: { field: pleuritic, op: eq, value: "是" }

  severe_sudden_pain:
    type: boolean
    when:
      all_of:
        - { field: sudden_onset, op: eq, value: "是" }
        - { field: pain_severity, op: gte, value: 7 }

  reproducible_tenderness:
    type: boolean
    when: { field: reproducible, op: eq, value: "是" }

# 3.4 红旗征（hard triggers）：医生写“必须立刻升级”的规则
red_flags:
  - id: RF_ACS
    name: "疑似急性冠脉综合征"
    message: "缺血性胸痛特征 + 放射/气促/大汗恶心等"
    when:
      all_of:
        - { concept: ischemic_like_pain, op: eq, value: true }
        - any_of:
            - { field: sob, op: eq, value: "是" }
            - { field: syncope, op: eq, value: "是" }
            - { field: neuro_deficit, op: eq, value: "是" }

  - id: RF_DISSECTION
    name: "疑似主动脉夹层"
    message: "突发剧痛 + 撕裂/刀割样"
    when:
      all_of:
        - { concept: severe_sudden_pain, op: eq, value: true }
        - { field: tearing_pain, op: eq, value: "是" }

# 3.5 证据规则（evidence rules）：医生主要写这一部分（支持/反对 + 强度档位）
# 每条规则可以同时影响多个病因。
evidence_rules:
  - id: E_ISCHEMIC_PAIN_SUPPORTS_ACS
    when: { concept: ischemic_like_pain, op: eq, value: true }
    affects:
      ACS: { direction: support, strength: strong }

  - id: E_PLEURITIC_SUPPORTS_PE_PTX
    when: { concept: pleuritic_pain, op: eq, value: true }
    affects:
      PE:  { direction: support, strength: moderate }
      PTX: { direction: support, strength: moderate }
      GERD:{ direction: oppose,  strength: weak }

  - id: E_REPRODUCIBLE_OPPOSES_ACS_SUPPORTS_MSK
    when: { concept: reproducible_tenderness, op: eq, value: true }
    affects:
      ACS: { direction: oppose,  strength: moderate }
      MSK: { direction: support, strength: strong }

  - id: E_RISK_CAD_SUPPORTS_ACS
    when: { field: risk_cad, op: eq, value: "是" }
    affects:
      ACS: { direction: support, strength: moderate }

# 3.6 缺失补问与保守策略（对高危字段）
# 目的：避免“未填=否”导致漏触发；医生只需声明哪些字段是高危必问。
missingness_policy:
  unknown_value: null
  critical_questions:
    - field: sob
      applies_to: [PE, PTX, ACS]
      if_missing: ask   # ask / assume_unknown / conservative_upgrade
    - field: syncope
      applies_to: [ACS, DISSECTION, PE]
      if_missing: ask

# 3.7 输出映射（病因 -> 科室 / 行动）
output_mapping:
  hypothesis_to_department:
    ACS: "cardiology"
    PE:  "pulmonology"
    PTX: "pulmonology"
    DISSECTION: "emergency"
    BOERHAAVE:  "emergency"
    GERD: "gastro"
    MSK:  "orthopedics"
    PANIC:"psych"

  department_meta:
    emergency:   { name: "急诊科", hint: "出现高危信号/无法排除急症时优先" }
    cardiology:  { name: "心内科/胸痛中心", hint: "疑似心肌缺血、心律失常等" }
    pulmonology: { name: "呼吸与危重症医学科（呼吸科）", hint: "咳嗽/呼吸困难/胸膜性疼痛等" }
    gastro:      { name: "消化内科", hint: "反酸烧心、与进食相关等" }
    orthopedics: { name: "骨科/疼痛科", hint: "按压或活动诱发、肌骨相关" }
    psych:       { name: "心理/精神科（或身心门诊）", hint: "惊恐发作样症状、焦虑相关" }
```

---

## 4. 医生写规则时的“最小工作量”范式（推荐工作流）

1. 选 profile：定义本场景各病因的先验（只需数量级正确，后续可校准）。
2. 定义 10–20 个 concept（把临床语言固化）：如 “缺血性胸痛”“胸膜性痛”“可重复压痛”“突发剧痛”等。
3. 写红旗征（hard triggers）：只写必须急诊/必须排除的少数条（高敏感）。
4. 写证据条目（evidence rules）：每条只需写“支持/反对 + 强度档位”，不要写数值。
5. 声明 critical_questions：哪些高危字段缺失时必须补问。

---

## 5. 引擎应当自动生成的可审计输出（医生不手写，但必须可见）

对每个结论，输出：

* 触发的红旗征列表（若有）
* 各高危病因的：prior、posterior、主要证据贡献（按 |logLR| 排序 Top-N）
* “为什么推荐该科室”：来源于哪个病因后验最高/证据最强
* “缺失项提醒”：哪些 critical_questions 未回答导致不确定性上升（并提示补问/保守升级）

---

## 6. 这套模式相对“加分总和阈值”的关键差异（避免概念混淆）

* 不再用 GI/MSK/Psych 的“像不像”去推高紧急度；紧急度由危险病因后验或红旗征决定。
* 证据可以是反向的（oppose），避免只有加分导致的单向累积偏误。
* profile 显式承载“先验知识”，医生不需要在每条规则里重复表达“本院更常见/更少见”。