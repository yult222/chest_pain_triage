# Chest Pain Triage MVP (Streamlit + DeepSeek + Rules)

> ⚠️ Disclaimer: This project is a demo for **triage assistance** only. It does **not** diagnose.
> If chest pain is severe or accompanied by shortness of breath, sweating, fainting, etc., seek emergency care.

## 1) Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set env vars:

```bash
export DEEPSEEK_API_KEY=...        # required for LLM extraction/summaries
export DEEPSEEK_BASE_URL=https://api.deepseek.com
export DEEPSEEK_MODEL=deepseek-chat
```

## 2) Build the 3D component (optional)

If you want the clickable 3D mannequin:

```bash
cd components/body3d/frontend
npm install
npm run build
```

Then run Streamlit from project root:

```bash
cd ../../../
streamlit run app.py
```

If you skip building the component, the app will fall back to a dropdown for pain location.

## 3) Knowledge base

Rules live in `knowledge_base/chest_pain_rules_v0_1.json`.
- `red_flags`: emergency popups
- `score_rules`: scoring for cardiology/pulmonology/gastro/...
- `dept_mapping` + `departments`: mapping to departments

Clinicians can iterate on this JSON without touching Python code.
