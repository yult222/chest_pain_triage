from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class Body3DWidget(QWidget):
    region_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source_pixmap = QPixmap(
            str((Path(__file__).resolve().parent.parent / "image.png").resolve())
        )

        self._image_label = QLabel(self)
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setMinimumHeight(220)
        self._image_label.setMaximumHeight(340)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._image_label)

        if self._source_pixmap.isNull():
            self._image_label.setText("数字人图片加载失败。")
            self._image_label.setWordWrap(True)
            return

        self._refresh_pixmap()

    def clear_selection(self) -> None:
        return

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if not self._source_pixmap.isNull():
            self._refresh_pixmap()

    def _refresh_pixmap(self) -> None:
        target_size = self._image_label.size()
        if target_size.width() <= 0 or target_size.height() <= 0:
            return

        self._image_label.setPixmap(
            self._source_pixmap.scaled(
                target_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )
