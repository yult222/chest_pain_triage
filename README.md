# Chest Pain Triage MVP (PySide6 Desktop App)

> Disclaimer: This project is for **triage assistance** only. It does **not** diagnose.
> If chest pain is severe or accompanied by shortness of breath, sweating, fainting, etc., seek emergency care immediately.

## 1) Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

Set environment variables:

```bash
export DEEPSEEK_API_KEY=...        # Optional: enables LLM extraction/summaries
export DEEPSEEK_BASE_URL=https://api.deepseek.com
export DEEPSEEK_MODEL=deepseek-chat
```

## 2) Run

From project root:

```bash
python app.py
```

The app now runs as a local desktop GUI (PySide6), without Streamlit.

## 3) 3D pain-location selector

- The app uses Qt WebEngine (`QWebEngineView`) to render the embedded 3D selector.
- If Qt WebEngine is unavailable in your runtime, the app **automatically falls back** to the location dropdown.

## 4) Knowledge base

Rules live in `knowledge_base/chest_pain_rules_v0_1.json`.

- `red_flags`: emergency triggers
- `score_rules`: system-level scoring
- `dept_mapping` + `departments`: department recommendations

Clinicians can iterate on this JSON without changing Python business logic.
