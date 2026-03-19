from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QWidget

APP_STYLE_SHEET = """
QMainWindow, QWidget {
    background: #eef4f8;
    color: #18324b;
    font-family: "Microsoft YaHei UI", "Segoe UI", "Microsoft YaHei";
    font-size: 14px;
}

QWidget[surface="hero"] {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #f7fbfd, stop: 0.6 #edf6f7, stop: 1 #e8f2f7);
    border: 1px solid #d7e5eb;
    border-radius: 24px;
}

QWidget[surface="card"] {
    background: #ffffff;
    border: 1px solid #d9e6ed;
    border-radius: 20px;
}

QWidget[surface="subtleCard"] {
    background: #f6fafc;
    border: 1px solid #dbe7ee;
    border-radius: 16px;
}

QWidget[surface="dangerCard"] {
    background: #fff4f2;
    border: 1px solid #efc1ba;
    border-radius: 20px;
}

QWidget[surface="card"] QLabel,
QWidget[surface="hero"] QLabel,
QWidget[surface="subtleCard"] QLabel,
QWidget[surface="dangerCard"] QLabel {
    background: transparent;
}

QLabel[textRole="heroTitle"] {
    font-size: 30px;
    font-weight: 700;
    color: #102b41;
}

QLabel[textRole="heroSubtitle"] {
    font-size: 15px;
    color: #537082;
}

QLabel[textRole="sectionTitle"] {
    font-size: 18px;
    font-weight: 700;
    color: #12314b;
}

QLabel[textRole="sectionDescription"] {
    color: #678296;
}

QLabel[textRole="fieldLabel"] {
    font-size: 13px;
    font-weight: 600;
    color: #456378;
}

QLabel[textRole="caption"] {
    font-size: 13px;
    color: #698599;
}

QLabel[textRole="summaryTitle"] {
    font-size: 28px;
    font-weight: 700;
    color: #102b41;
}

QLabel[textRole="summaryMeta"] {
    color: #527082;
}

QLabel[textRole="dangerTitle"] {
    font-size: 18px;
    font-weight: 700;
    color: #8a1f17;
}

QLabel[textRole="dangerText"] {
    color: #9c2a1f;
}

QLabel[textRole="successText"] {
    color: #1f6e45;
}

QLabel[textRole="warningText"] {
    color: #8b5b00;
}

QLabel[bannerRole="notice"] {
    background: #f8fbec;
    color: #4f5c11;
    border: 1px solid #dbe2b0;
    border-radius: 16px;
    padding: 12px 14px;
    font-size: 13px;
}

QLabel[chipRole="neutral"],
QLabel[chipRole="info"],
QLabel[chipRole="success"],
QLabel[chipRole="warning"],
QLabel[chipRole="danger"] {
    border-radius: 999px;
    padding: 6px 12px;
    font-size: 13px;
    font-weight: 700;
}

QLabel[chipRole="neutral"] {
    background: #edf3f7;
    border: 1px solid #d8e3ea;
    color: #4b6578;
}

QLabel[chipRole="info"] {
    background: #e0f1f4;
    border: 1px solid #bbdfe5;
    color: #0d6368;
}

QLabel[chipRole="success"] {
    background: #e5f5eb;
    border: 1px solid #bfe0cd;
    color: #1f6e45;
}

QLabel[chipRole="warning"] {
    background: #fff3dd;
    border: 1px solid #efd2a0;
    color: #8b5b00;
}

QLabel[chipRole="danger"] {
    background: #fde8e5;
    border: 1px solid #efb7ae;
    color: #9c2a1f;
}

QScrollArea {
    border: none;
    background: transparent;
}

QSplitter::handle {
    background: transparent;
}

QSplitter::handle:horizontal {
    width: 12px;
}

QLineEdit,
QComboBox,
QSpinBox,
QTextEdit,
QPlainTextEdit,
QListWidget {
    background: #f8fbfc;
    border: 1px solid #d4e2ea;
    border-radius: 14px;
    padding: 8px 10px;
    color: #18324b;
    selection-background-color: #cfecee;
}

QLineEdit:focus,
QComboBox:focus,
QSpinBox:focus,
QTextEdit:focus,
QPlainTextEdit:focus,
QListWidget:focus {
    border: 1px solid #3f98a0;
}

QLineEdit:read-only,
QComboBox:disabled,
QLineEdit:disabled,
QSpinBox:disabled,
QTextEdit:disabled,
QPlainTextEdit:disabled,
QListWidget:disabled {
    background: #f1f5f7;
    color: #8398a8;
}

QTextEdit,
QPlainTextEdit {
    padding-top: 10px;
}

QPlainTextEdit[panelRole="log"] {
    background: #f3f8fa;
    border: 1px solid #dbe7ee;
}

QComboBox::drop-down,
QSpinBox::drop-down {
    width: 28px;
    border: none;
    background: transparent;
}

QComboBox QAbstractItemView {
    background: #ffffff;
    border: 1px solid #d4e2ea;
    selection-background-color: #d7eef0;
    outline: 0;
}

QPushButton {
    border-radius: 14px;
    padding: 10px 16px;
    font-weight: 700;
    border: 1px solid transparent;
}

QPushButton[buttonRole="primary"] {
    background: #167d83;
    color: #ffffff;
}

QPushButton[buttonRole="primary"]:hover {
    background: #116f75;
}

QPushButton[buttonRole="secondary"] {
    background: #edf4f7;
    color: #17405a;
    border: 1px solid #d0e0e8;
}

QPushButton[buttonRole="secondary"]:hover {
    background: #e3edf2;
}

QPushButton[buttonRole="ghost"] {
    background: transparent;
    color: #4b7189;
    border: 1px solid #d7e5ed;
}

QPushButton[buttonRole="ghost"]:hover {
    background: #f2f7fa;
}

QPushButton:disabled {
    background: #dce6eb;
    color: #8ba0ad;
    border-color: #dce6eb;
}

QToolButton[buttonRole="section"] {
    background: #f5fafc;
    border: 1px solid #d9e7ee;
    border-radius: 14px;
    padding: 12px 14px;
    font-size: 15px;
    font-weight: 700;
    color: #12314b;
    text-align: left;
}

QToolButton[buttonRole="section"]:hover {
    background: #eef6f8;
}

QToolButton[buttonRole="section"]:checked {
    background: #eaf4f6;
    border-color: #bfd8dc;
    color: #0f5f65;
}

QCheckBox {
    spacing: 10px;
    color: #18324b;
}

QTabWidget::pane {
    background: #ffffff;
    border: 1px solid #d9e6ed;
    border-radius: 18px;
    margin-top: 8px;
}

QTabBar::tab {
    background: #e7eff4;
    color: #527082;
    border: none;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    padding: 10px 16px;
    margin-right: 6px;
    min-width: 82px;
}

QTabBar::tab:selected {
    background: #ffffff;
    color: #12314b;
    font-weight: 700;
}

QListWidget {
    padding: 6px;
}

QListWidget::item {
    padding: 10px 12px;
    margin: 2px 0;
    border-radius: 10px;
}

QListWidget::item:selected {
    background: #dff0f2;
    color: #12314b;
}

QScrollBar:vertical {
    background: transparent;
    width: 12px;
    margin: 4px;
}

QScrollBar::handle:vertical {
    background: #cad8e0;
    min-height: 32px;
    border-radius: 6px;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical,
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: none;
    border: none;
}

QStatusBar {
    background: #ffffff;
    border-top: 1px solid #d8e5ec;
    color: #5c7588;
}
"""


def apply_medical_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    font = QFont("Microsoft YaHei UI", 10)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)
    app.setStyleSheet(APP_STYLE_SHEET)


def repolish(widget: QWidget) -> None:
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()
