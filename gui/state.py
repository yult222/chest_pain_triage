from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from triage.app_service import GenerationResult
from triage.schemas import CaseRecord


@dataclass
class AppState:
    rf_active: bool = False
    rf_sig_shown: Optional[str] = None
    selected_profile: Optional[str] = None
    last_case: Optional[CaseRecord] = None
    last_result: Optional[GenerationResult] = None
