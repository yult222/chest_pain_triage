from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort extraction of the first JSON object in `text`.

    Many LLMs sometimes wrap JSON in markdown fences or add extra commentary.
    This helper tries to locate the first {...} block and parse it.
    """
    if not text:
        return None

    # Remove markdown code fences
    cleaned = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE).replace("```", "")
    cleaned = cleaned.strip()

    # Fast path: whole string is JSON
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # Find first JSON object
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        return None

    snippet = match.group(0)
    try:
        obj = json.loads(snippet)
        if isinstance(obj, dict):
            return obj
    except Exception:
        return None

    return None


def clamp_int(value: Any, low: int, high: int, default: int) -> int:
    try:
        v = int(value)
        return max(low, min(high, v))
    except Exception:
        return default
