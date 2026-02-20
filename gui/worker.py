from __future__ import annotations

import traceback

from PySide6.QtCore import QObject, Signal, Slot

from triage.app_service import generate_case_record
from triage.rules_engine import KnowledgeBase
from triage.schemas import ChestPainAnswers, PatientInfo


class GenerateCaseWorker(QObject):
    progress = Signal(str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        kb: KnowledgeBase,
        patient: PatientInfo,
        answers: ChestPainAnswers,
        symptom_text: str,
        has_key: bool,
    ) -> None:
        super().__init__()
        self._kb = kb
        self._patient = patient
        self._answers = answers
        self._symptom_text = symptom_text
        self._has_key = has_key

    @Slot()
    def run(self) -> None:
        try:
            result = generate_case_record(
                kb=self._kb,
                patient=self._patient,
                answers=self._answers,
                symptom_text=self._symptom_text,
                has_key=self._has_key,
                progress=self.progress.emit,
            )
            self.finished.emit(result)
        except Exception:
            self.failed.emit(traceback.format_exc())
