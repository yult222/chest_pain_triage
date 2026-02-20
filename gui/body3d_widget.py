from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

try:
    from PySide6.QtWebChannel import QWebChannel
    from PySide6.QtWebEngineWidgets import QWebEngineView

    WEBENGINE_AVAILABLE = True
except Exception:
    QWebChannel = None  # type: ignore[assignment]
    QWebEngineView = None  # type: ignore[assignment]
    WEBENGINE_AVAILABLE = False


class Body3DBridge(QObject):
    region_selected = Signal(str)

    @Slot(str)
    def selectRegion(self, region: str) -> None:
        self.region_selected.emit(region)


class Body3DWidget(QWidget):
    region_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if not WEBENGINE_AVAILABLE:
            fallback = QLabel("未检测到 Qt WebEngine，3D 点击功能不可用。已自动降级为下拉选择。")
            fallback.setWordWrap(True)
            layout.addWidget(fallback)
            return

        self._bridge = Body3DBridge()
        self._bridge.region_selected.connect(self.region_selected.emit)

        self._channel = QWebChannel(self)
        self._channel.registerObject("bridge", self._bridge)

        self._view = QWebEngineView(self)
        self._view.page().setWebChannel(self._channel)

        html_path = (Path(__file__).resolve().parent / "assets" / "body3d.html").resolve()
        self._view.setUrl(QUrl.fromLocalFile(str(html_path)))
        layout.addWidget(self._view)

    def clear_selection(self) -> None:
        if self._view is not None:
            self._view.page().runJavaScript("window.clearSelection && window.clearSelection();")
