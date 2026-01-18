from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv
load_dotenv()

@dataclass(frozen=True)
class Settings:
    """Runtime settings.

    We use DeepSeek's OpenAI-compatible API. Official docs:
    - base_url: https://api.deepseek.com (or https://api.deepseek.com/v1)
    - models: deepseek-chat, deepseek-reasoner

    IMPORTANT: Do NOT hard-code API keys in code. Use environment variables or Streamlit secrets.
    """

    # DeepSeek/OpenAI compatible
    api_key: str = os.getenv("DEEPSEEK_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    base_url: str = os.getenv("DEEPSEEK_BASE_URL", os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com"))
    model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # Behavior
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    llm_timeout_sec: int = int(os.getenv("LLM_TIMEOUT_SEC", "30"))

    # Knowledge base
    rules_path: str = os.getenv(
        "RULES_PATH",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge_base", "chest_pain_rules_v0_1.json"),
    )


settings = Settings()
