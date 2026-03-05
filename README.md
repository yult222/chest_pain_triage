# Chest Pain Triage MVP (PySide6 Desktop App)

> Disclaimer: this project is for triage assistance only. It does not diagnose.
> If chest pain is severe or accompanied by shortness of breath, sweating, fainting, etc., seek emergency care immediately.

## 1) Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

Set environment variables (optional for LLM):

```bash
export DEEPSEEK_API_KEY=...
export DEEPSEEK_BASE_URL=https://api.deepseek.com
export DEEPSEEK_MODEL=deepseek-chat
```

## 2) Run

```bash
python app.py
```

## 3) Rule Engines (v0.1 + v0.2)

The app supports two rule engines and auto-selects by rule file `version`:

- `v0.1`: score-sum rules (`knowledge_base/chest_pain_rules_v0_1.json`)
- `v0.2`: prior + evidence (LR/log-odds) rules (`knowledge_base/chest_pain_rules_v0_2.yaml`)

Default is now `v0.2`. To rollback to v0.1:

```bash
export RULES_PATH=knowledge_base/chest_pain_rules_v0_1.json
```

## 4) Clinician Authoring Workflow (v0.2)

Recommended minimal workflow:

1. Pick a `profile` and define `priors` + triage thresholds.
2. Define reusable `concepts` (clinical language -> boolean conditions).
3. Add a few `red_flags` (hard emergency triggers).
4. Add `evidence_rules` using `support/oppose + strength`.
5. Maintain `missingness_policy.critical_questions`.

## 5) Validate Rules

Before launching GUI, validate rule files:

```bash
python -m triage.rules_cli validate --rules knowledge_base/chest_pain_rules_v0_2.yaml
```

Validation includes:

- field name legality
- concept reference existence
- hypothesis consistency across profiles/rules/mappings
- threshold ranges
- strength reference existence
- danger hypotheses subset checks
- missingness policy legality

Error format:

- `file=...`
- `version=...`
- `error_at=...` (first failed path)
- `detail=...`

## 6) Common Rule Errors

1. `strength` references unknown scale key  
   Fix: ensure `affects.*.strength` exists in `strength_scale`.

2. `concept` references unknown name  
   Fix: define concept under `concepts` first.

3. hypothesis appears in `evidence_rules` but not in any `profiles.*.priors`  
   Fix: add prior for that hypothesis in every intended profile.

4. missing `output_mapping.hypothesis_to_department` entry  
   Fix: map all hypotheses to departments.

## 7) 3D pain-location selector

- Uses Qt WebEngine (`QWebEngineView`) when available.
- Falls back to dropdown when WebEngine is unavailable.
