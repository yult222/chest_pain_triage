from __future__ import annotations

import json
from datetime import datetime
from typing import Optional, get_args

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from triage.app_service import GenerationResult, evaluate_realtime_alert
from triage.config import settings
from triage.exporter import export_case_json, export_case_pdf
from triage.rules_engine import load_knowledge_base
from triage.schemas import ChestPainAnswers, PatientInfo

from .body3d_widget import Body3DWidget
from .state import AppState
from .worker import GenerateCaseWorker


class CollapsibleSection(QWidget):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._toggle = QToolButton(self)
        self._toggle.setText(title)
        self._toggle.setCheckable(True)
        self._toggle.setChecked(False)
        self._toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._toggle.setArrowType(Qt.RightArrow)

        self._content = QWidget(self)
        self._content.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._toggle)
        layout.addWidget(self._content)

        self._toggle.toggled.connect(self._on_toggled)

    def setContentLayout(self, content_layout) -> None:  # noqa: N802 (Qt style)
        self._content.setLayout(content_layout)

    def _on_toggled(self, checked: bool) -> None:
        self._toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        self._content.setVisible(checked)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("胸痛智能分诊系统（PySide6）")
        self._landscape_enforced = False

        self.state = AppState()
        self._worker_thread: Optional[QThread] = None
        self._worker: Optional[GenerateCaseWorker] = None
        self._selected_3d_region: Optional[str] = None
        self.profile_combo: Optional[QComboBox] = None

        self.yes_no_options = list(get_args(ChestPainAnswers.model_fields["sudden_onset"].annotation))
        self.pain_quality_options = list(get_args(ChestPainAnswers.model_fields["pain_quality"].annotation))

        sex_options_from_type: list[str] = []
        sex_annotation = PatientInfo.model_fields["sex"].annotation
        for arg in get_args(sex_annotation):
            if isinstance(arg, str):
                sex_options_from_type.append(arg)
                continue
            sex_options_from_type.extend([value for value in get_args(arg) if isinstance(value, str)])

        self.sex_options = ["未填", *(sex_options_from_type or ["男", "女", "其他/不便透露"])]
        self.pain_location_options = [
            "未选择",
            "胸骨后/正中胸口",
            "左胸",
            "右胸",
            "上腹/心窝",
            "背部/肩胛间",
            "左肩/左上肢",
            "右肩/右上肢",
        ]
        self.answer_widgets: dict[str, QComboBox] = {}

        try:
            self.kb = load_knowledge_base(settings.rules_path)
        except Exception as exc:
            QMessageBox.critical(self, "启动失败", f"无法加载规则库：{exc}")
            raise

        self.state.selected_profile = self.kb.default_profile

        self._build_ui()
        self._bind_signals()
        self._update_consent_state()
        self._refresh_debug_output()
        self._apply_initial_window_geometry()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if not self._landscape_enforced:
            self._landscape_enforced = True
            self._apply_initial_window_geometry()

    def _apply_initial_window_geometry(self) -> None:
        requested_min_width = 980
        requested_min_height = 660
        target_width = 1180
        target_height = 780

        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            safe_width = max(900, available.width() - 48)
            safe_height = max(620, available.height() - 72)
            min_width = min(requested_min_width, safe_width)
            min_height = min(requested_min_height, safe_height)
            width = max(min_width, min(target_width, safe_width))
            height = max(min_height, min(target_height, safe_height))
            if width <= height:
                width = min(safe_width, max(min_width, height + 180))
        else:
            min_width = requested_min_width
            min_height = requested_min_height
            width = target_width
            height = target_height

        self.setMinimumSize(min_width, min_height)
        self.resize(width, height)

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)

        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        splitter = QSplitter(Qt.Horizontal, self)
        root_layout.addWidget(splitter)

        left_scroll = QScrollArea(self)
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        left_panel = QWidget()
        left_scroll.setWidget(left_panel)

        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(8)

        title = QLabel("胸痛智能分诊工作台")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        left_layout.addWidget(title)

        safety_banner = QLabel(
            "本系统仅用于分诊辅助，不能替代医生诊断或急救处置。"
            "若胸痛严重或伴呼吸困难、大汗、晕厥、神经功能缺失，请立即急诊评估或呼叫急救。"
        )
        safety_banner.setWordWrap(True)
        left_layout.addWidget(safety_banner)

        self.consent_checkbox = QCheckBox(
            "我理解并同意：该系统仅作分诊参考，不能替代医生诊断；如有急症我会优先就医或呼叫急救。"
        )
        left_layout.addWidget(self.consent_checkbox)

        self.gated_container = QWidget(self)
        gated_layout = QVBoxLayout(self.gated_container)
        gated_layout.setContentsMargins(0, 0, 0, 0)
        gated_layout.setSpacing(8)

        top_grid = QGridLayout()
        top_grid.setHorizontalSpacing(10)
        top_grid.setVerticalSpacing(10)
        top_grid.setColumnStretch(0, 1)
        top_grid.setColumnStretch(1, 1)
        top_grid.addWidget(self._build_basic_info_group(), 0, 0)
        top_grid.addWidget(self._build_pain_location_group(), 0, 1)
        gated_layout.addLayout(top_grid)

        gated_layout.addWidget(self._build_symptom_group())
        gated_layout.addWidget(self._build_questionnaire_section())

        self.realtime_alert_banner = QLabel(
            "系统实时检测到可能的高危信号（红旗征）。建议立即急诊评估或呼叫急救。"
        )
        self.realtime_alert_banner.setWordWrap(True)
        self.realtime_alert_banner.setVisible(False)
        gated_layout.addWidget(self.realtime_alert_banner)

        button_row = QHBoxLayout()
        self.generate_button = QPushButton("生成分诊建议")
        self.generate_button.setMinimumHeight(34)
        self.export_json_button = QPushButton("导出 JSON")
        self.export_pdf_button = QPushButton("导出 PDF")
        self.export_json_button.setEnabled(False)
        self.export_pdf_button.setEnabled(False)
        button_row.addWidget(self.generate_button)
        button_row.addWidget(self.export_json_button)
        button_row.addWidget(self.export_pdf_button)
        button_row.addStretch(1)
        gated_layout.addLayout(button_row)

        self.progress_log = QPlainTextEdit()
        self.progress_log.setReadOnly(True)
        self.progress_log.setPlaceholderText("运行进度将显示在这里...")
        self.progress_log.setMaximumHeight(96)
        gated_layout.addWidget(self.progress_log)

        gated_layout.addWidget(self._build_result_group())
        left_layout.addWidget(self.gated_container)
        left_layout.addStretch(1)

        sidebar = self._build_sidebar_panel()
        splitter.addWidget(left_scroll)
        splitter.addWidget(sidebar)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([860, 300])

        self.statusBar().showMessage("就绪")

    def _build_basic_info_group(self) -> QGroupBox:
        group = QGroupBox("1. 患者信息")
        form = QFormLayout(group)
        form.setSpacing(10)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如：张三")

        self.sex_combo = QComboBox()
        self.sex_combo.addItems(self.sex_options)

        self.age_spin = QSpinBox()
        self.age_spin.setRange(0, 120)
        self.age_spin.setValue(30)

        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("可选，便于病例导出")

        form.addRow("姓名", self.name_edit)
        form.addRow("性别", self.sex_combo)
        form.addRow("年龄", self.age_spin)
        form.addRow("联系方式", self.phone_edit)
        return group

    def _build_pain_location_group(self) -> QGroupBox:
        group = QGroupBox("2. 疼痛位置")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        caption = QLabel("请参考下图，并在下方选择最主要的疼痛位置。")
        caption.setWordWrap(True)
        layout.addWidget(caption)

        self.body3d_widget = Body3DWidget(self)
        self.body3d_widget.setMinimumHeight(250)
        layout.addWidget(self.body3d_widget)

        self.pain_location_combo = QComboBox()
        self.pain_location_combo.addItems(self.pain_location_options)
        layout.addWidget(QLabel("疼痛位置（备选）"))
        layout.addWidget(self.pain_location_combo)

        return group

    def _build_symptom_group(self) -> QGroupBox:
        group = QGroupBox("3. 自述症状")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        prompt = QLabel("建议优先补充自然语言描述，例如开始时间、性质、持续时长、放射痛、伴随症状、既往史和用药情况。")
        prompt.setWordWrap(True)
        layout.addWidget(prompt)

        self.symptom_text_edit = QTextEdit()
        self.symptom_text_edit.setMinimumHeight(120)
        self.symptom_text_edit.setPlaceholderText("请尽量完整描述胸痛表现和伴随症状。")
        layout.addWidget(self.symptom_text_edit)

        return group

    def _build_questionnaire_section(self) -> QWidget:
        section = CollapsibleSection("4. 症状问卷（可选）")
        content = QFormLayout()
        content.setSpacing(10)

        self.pain_severity_combo = QComboBox()
        self.pain_severity_combo.addItem("未选择")
        self.pain_severity_combo.addItems([str(i) for i in range(11)])
        content.addRow("疼痛程度（0-10）", self.pain_severity_combo)

        self.pain_quality_combo = QComboBox()
        self.pain_quality_combo.addItems(self.pain_quality_options)
        self.answer_widgets["pain_quality"] = self.pain_quality_combo
        content.addRow("疼痛性质", self.pain_quality_combo)

        self._add_yes_no_row(content, "sudden_onset", "是否突然发生？")
        self._add_yes_no_row(content, "trauma", "是否有外伤/撞击/跌倒后出现？")
        self._add_yes_no_row(content, "tearing_pain", "是否明显撕裂/刀割样并可放射到背部？")
        self._add_yes_no_row(content, "pleuritic", "是否深呼吸/咳嗽时更痛？")
        self._add_yes_no_row(content, "exertional", "是否运动/上楼/走快时更明显？")
        self._add_yes_no_row(content, "relieved_by_rest", "是否休息可缓解？")
        self._add_yes_no_row(content, "reproducible", "按压胸壁/转动身体可诱发或复制疼痛？")
        self._add_yes_no_row(content, "sob", "是否气促/呼吸困难？")
        self._add_yes_no_row(content, "radiation", "是否放射到左臂/下颌/背部等？")
        self._add_yes_no_row(content, "sweat_nausea", "是否大汗/恶心/呕吐？")
        self._add_yes_no_row(content, "palpitations", "是否心慌/心跳不齐？")
        self._add_yes_no_row(content, "syncope", "是否晕厥/眼前发黑/快要晕倒？")
        self._add_yes_no_row(content, "neuro_deficit", "是否口齿不清/偏侧无力或麻木等？")
        self._add_yes_no_row(content, "cough_fever", "是否咳嗽或发热？")
        self._add_yes_no_row(content, "hemoptysis", "是否咯血？")
        self._add_yes_no_row(content, "heartburn", "是否烧心/反酸？")
        self._add_yes_no_row(content, "after_meal", "是否与进食相关？")
        self._add_yes_no_row(content, "relieved_by_antacid", "服用抑酸/胃药后缓解？")
        self._add_yes_no_row(content, "vomiting", "是否出现明显呕吐？")
        self._add_yes_no_row(content, "worse_with_movement", "活动/姿势变化时更痛？")
        self._add_yes_no_row(content, "panic", "是否像惊恐发作？")
        self._add_yes_no_row(content, "stress_trigger", "是否在情绪/压力后诱发？")
        self._add_yes_no_row(content, "risk_cad", "是否存在心血管危险因素/既往心脏病史？")
        self._add_yes_no_row(content, "immobilization", "近期手术/久坐久卧/长途旅行？")
        self._add_yes_no_row(content, "leg_swelling", "是否单侧下肢肿胀/疼痛？")

        section.setContentLayout(content)
        return section

    def _build_result_group(self) -> QGroupBox:
        group = QGroupBox("分诊建议")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.level_label = QLabel("尚未生成")
        self.level_label.setStyleSheet("font-size: 18px; font-weight: 700;")
        layout.addWidget(self.level_label)

        layout.addWidget(QLabel("推荐就诊科室（Top 3）"))
        self.dept_list = QListWidget()
        self.dept_list.setMaximumHeight(88)
        layout.addWidget(self.dept_list)

        layout.addWidget(QLabel("红旗征触发项"))
        self.red_flags_output = QPlainTextEdit()
        self.red_flags_output.setReadOnly(True)
        self.red_flags_output.setMaximumHeight(88)
        layout.addWidget(self.red_flags_output)

        layout.addWidget(QLabel("高危病因后验 Top-N"))
        self.posterior_output = QPlainTextEdit()
        self.posterior_output.setReadOnly(True)
        self.posterior_output.setMaximumHeight(88)
        layout.addWidget(self.posterior_output)

        layout.addWidget(QLabel("关键证据贡献 Top-N"))
        self.evidence_output = QPlainTextEdit()
        self.evidence_output.setReadOnly(True)
        self.evidence_output.setMaximumHeight(88)
        layout.addWidget(self.evidence_output)

        layout.addWidget(QLabel("关键缺失项提醒"))
        self.missing_output = QPlainTextEdit()
        self.missing_output.setReadOnly(True)
        self.missing_output.setMaximumHeight(72)
        layout.addWidget(self.missing_output)

        layout.addWidget(QLabel("给患者的说明（LLM）"))
        self.patient_summary_output = QPlainTextEdit()
        self.patient_summary_output.setReadOnly(True)
        self.patient_summary_output.setMaximumHeight(96)
        layout.addWidget(self.patient_summary_output)

        layout.addWidget(QLabel("规则引擎解释（可审计）"))
        self.reasons_output = QPlainTextEdit()
        self.reasons_output.setReadOnly(True)
        self.reasons_output.setMaximumHeight(108)
        layout.addWidget(self.reasons_output)

        layout.addWidget(QLabel("调试信息"))
        self.debug_output = QPlainTextEdit()
        self.debug_output.setReadOnly(True)
        self.debug_output.setVisible(False)
        self.debug_output.setMaximumHeight(180)
        layout.addWidget(self.debug_output)

        return group

    def _build_sidebar_panel(self) -> QWidget:
        panel = QWidget(self)
        panel.setMinimumWidth(260)
        panel.setMaximumWidth(320)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        title = QLabel("配置")
        title.setStyleSheet("font-size:18px; font-weight:700;")
        layout.addWidget(title)

        caption = QLabel("DeepSeek 使用 OpenAI 兼容接口。")
        caption.setWordWrap(True)
        layout.addWidget(caption)

        base_url = QLineEdit(settings.base_url)
        base_url.setReadOnly(True)
        model = QLineEdit(settings.model)
        model.setReadOnly(True)

        layout.addWidget(QLabel("DEEPSEEK_BASE_URL"))
        layout.addWidget(base_url)
        layout.addWidget(QLabel("DEEPSEEK_MODEL"))
        layout.addWidget(model)

        has_key = bool(settings.api_key)
        self.api_key_status = QLabel(
            "API Key 状态：已配置" if has_key else "API Key 状态：未配置（将降级为仅规则分诊）"
        )
        self.api_key_status.setWordWrap(True)
        layout.addWidget(self.api_key_status)

        if self.kb.engine_mode == "v2" and self.kb.profile_ids:
            layout.addWidget(QLabel("规则 Profile"))
            self.profile_combo = QComboBox()
            self.profile_combo.addItems(self.kb.profile_ids)
            selected_profile = self.state.selected_profile or self.kb.profile_ids[0]
            idx = self.profile_combo.findText(selected_profile)
            if idx >= 0:
                self.profile_combo.setCurrentIndex(idx)
            self.state.selected_profile = self.profile_combo.currentText()
            layout.addWidget(self.profile_combo)
        else:
            self.profile_combo = None
            self.state.selected_profile = None

        self.debug_checkbox = QCheckBox("显示调试信息")
        self.debug_checkbox.setChecked(False)
        layout.addWidget(self.debug_checkbox)

        layout.addStretch(1)
        return panel

    def _add_yes_no_row(self, layout: QFormLayout, field: str, label: str) -> None:
        combo = QComboBox()
        combo.addItems(self.yes_no_options)
        self.answer_widgets[field] = combo
        layout.addRow(label, combo)

    def _bind_signals(self) -> None:
        self.consent_checkbox.toggled.connect(self._update_consent_state)
        self.generate_button.clicked.connect(self._on_generate_clicked)
        self.export_json_button.clicked.connect(self._on_export_json_clicked)
        self.export_pdf_button.clicked.connect(self._on_export_pdf_clicked)
        self.debug_checkbox.toggled.connect(self._refresh_debug_output)
        if self.profile_combo is not None:
            self.profile_combo.currentTextChanged.connect(self._on_profile_changed)

        self.pain_severity_combo.currentIndexChanged.connect(self._on_inputs_changed)
        self.pain_quality_combo.currentIndexChanged.connect(self._on_inputs_changed)
        self.pain_location_combo.currentIndexChanged.connect(self._on_inputs_changed)
        self.symptom_text_edit.textChanged.connect(self._on_inputs_changed)

        for combo in self.answer_widgets.values():
            combo.currentIndexChanged.connect(self._on_inputs_changed)

        self.body3d_widget.region_selected.connect(self._on_3d_region_selected)

    def _update_consent_state(self, *_args) -> None:
        allowed = self.consent_checkbox.isChecked()
        self.gated_container.setEnabled(allowed)
        self.generate_button.setEnabled(allowed and self._worker_thread is None)
        if not allowed:
            self.statusBar().showMessage("请先勾选知情同意")
        else:
            self.statusBar().showMessage("就绪")
            self._on_inputs_changed()

    def _on_profile_changed(self, profile_id: str) -> None:
        self.state.selected_profile = profile_id or None
        self.state.rf_sig_shown = None
        self._on_inputs_changed()

    def _on_3d_region_selected(self, region: str) -> None:
        self._selected_3d_region = region
        self._on_inputs_changed()

    def _clear_3d_selection(self) -> None:
        self._selected_3d_region = None
        self.body3d_widget.clear_selection()
        self._on_inputs_changed()

    def _current_pain_location(self) -> Optional[str]:
        fallback = self.pain_location_combo.currentText()
        fallback_value = None if fallback == "未选择" else fallback
        return self._selected_3d_region or fallback_value

    def _collect_answers(self) -> ChestPainAnswers:
        severity_text = self.pain_severity_combo.currentText()
        pain_severity = None if severity_text == "未选择" else int(severity_text)

        values = {field: combo.currentText() for field, combo in self.answer_widgets.items()}
        return ChestPainAnswers(
            pain_location=self._current_pain_location(),
            pain_severity=pain_severity,
            **values,
        )

    def _collect_patient(self) -> PatientInfo:
        sex_value = self.sex_combo.currentText()
        return PatientInfo(
            name=self.name_edit.text().strip() or None,
            sex=None if sex_value == "未填" else sex_value,
            age=int(self.age_spin.value()),
            phone=self.phone_edit.text().strip() or None,
        )

    def _on_inputs_changed(self, *_args) -> None:
        if not self.consent_checkbox.isChecked() or self._worker_thread is not None:
            return

        try:
            answers_preview = self._collect_answers()
        except Exception:
            return

        alert = evaluate_realtime_alert(
            kb=self.kb,
            answers_preview=answers_preview,
            symptom_text=self.symptom_text_edit.toPlainText(),
            shown_signature=self.state.rf_sig_shown,
            profile_id=self.state.selected_profile,
        )

        if not alert.active:
            self.state.rf_active = False
            self.state.rf_sig_shown = None
            self.realtime_alert_banner.setVisible(False)
            return

        self.state.rf_active = True
        self.realtime_alert_banner.setVisible(True)

        if alert.should_popup and alert.signature:
            self.state.rf_sig_shown = alert.signature
            hit_lines = "\n".join(f"- {hit}" for hit in alert.hits)
            QMessageBox.warning(
                self,
                "紧急提醒（请优先就医）",
                "检测到可能的高危信号（红旗征）。建议立即急诊评估或呼叫急救。\n\n"
                f"触发项：\n{hit_lines}",
            )

    def _on_generate_clicked(self, checked: bool = False) -> None:
        _ = checked
        if not self.consent_checkbox.isChecked() or self._worker_thread is not None:
            return

        try:
            patient = self._collect_patient()
            answers = self._collect_answers()
        except Exception as exc:
            QMessageBox.critical(self, "输入错误", str(exc))
            return

        symptom_text = self.symptom_text_edit.toPlainText().strip()
        self.progress_log.clear()
        self._append_progress("开始生成分诊建议...")
        self._set_busy(True)

        self._worker_thread = QThread(self)
        self._worker = GenerateCaseWorker(
            kb=self.kb,
            patient=patient,
            answers=answers,
            symptom_text=symptom_text,
            profile_id=self.state.selected_profile,
            has_key=bool(settings.api_key),
        )
        self._worker.moveToThread(self._worker_thread)

        self._worker_thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._append_progress)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.failed.connect(self._on_worker_failed)

        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.failed.connect(self._worker_thread.quit)
        self._worker_thread.finished.connect(self._cleanup_worker)

        self._worker_thread.start()

    def _append_progress(self, message: str) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        self.progress_log.appendPlainText(f"[{now}] {message}")
        self.statusBar().showMessage(message)

    def _on_worker_finished(self, result: GenerationResult) -> None:
        self.state.last_result = result
        self.state.last_case = result.case
        self._render_result(result)
        self._refresh_debug_output()

        self.export_json_button.setEnabled(True)
        self.export_pdf_button.setEnabled(True)
        self._set_busy(False)

    def _on_worker_failed(self, trace: str) -> None:
        self._append_progress("生成失败")
        self._set_busy(False)
        QMessageBox.critical(
            self,
            "生成失败",
            "生成分诊建议时发生异常。\n\n"
            "请检查规则库、依赖与网络配置。\n\n"
            f"详情：\n{trace}",
        )

    def _cleanup_worker(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        if self._worker_thread is not None:
            self._worker_thread.deleteLater()
            self._worker_thread = None
        self.generate_button.setEnabled(self.consent_checkbox.isChecked())

    def _render_result(self, result: GenerationResult) -> None:
        triage = result.triage

        level_text = {
            "EMERGENCY": "高危/需急诊",
            "URGENT": "建议尽快就医（24小时内）",
            "ROUTINE": "可门诊就医（近期）",
        }.get(triage.level, triage.level)

        if triage.level == "EMERGENCY":
            self.level_label.setStyleSheet("font-size: 18px; font-weight: 700; color:#b01c1c;")
        elif triage.level == "URGENT":
            self.level_label.setStyleSheet("font-size: 18px; font-weight: 700; color:#8a5a00;")
        else:
            self.level_label.setStyleSheet("font-size: 18px; font-weight: 700; color:#175d2b;")
        self.level_label.setText(level_text)

        self.dept_list.clear()
        for index, dept in enumerate(result.top3_departments, start=1):
            self.dept_list.addItem(f"{index}. {dept}")

        if triage.red_flags:
            self.red_flags_output.setPlainText("\n".join(f"- {rf.name}：{rf.message}" for rf in triage.red_flags))
        else:
            self.red_flags_output.setPlainText("未触发规则红旗征")

        if triage.posterior_breakdown:
            top_posterior = sorted(triage.posterior_breakdown.items(), key=lambda item: item[1], reverse=True)[:5]
            self.posterior_output.setPlainText(
                "\n".join(f"- {hypothesis}: {probability:.3f}" for hypothesis, probability in top_posterior)
            )
        else:
            self.posterior_output.setPlainText("当前规则引擎未提供后验概率")

        if triage.evidence_top:
            evidence_lines = [
                f"- {item.hypothesis} <- {item.rule_id} ({item.direction}, LR={item.lr:.2f}, logLR={item.log_lr:+.3f})"
                for item in triage.evidence_top[:5]
            ]
            self.evidence_output.setPlainText("\n".join(evidence_lines))
        else:
            self.evidence_output.setPlainText("暂无关键证据贡献")

        if triage.missing_critical_questions:
            self.missing_output.setPlainText(
                "\n".join(f"- {field}（建议补问）" for field in triage.missing_critical_questions)
            )
        else:
            self.missing_output.setPlainText("无关键缺失项")

        self.patient_summary_output.setPlainText(
            result.case.llm_summary_for_patient or "未生成（未配置 API Key 或 LLM 调用失败）"
        )

        reason_lines = [f"引擎模式：{triage.engine_mode}"]
        if triage.profile_id:
            reason_lines.append(f"规则 Profile：{triage.profile_id}")
        reason_lines.extend([f"- {reason}" for reason in triage.reasons])
        self.reasons_output.setPlainText("\n".join(reason_lines) if reason_lines else "无")

    def _refresh_debug_output(self, *_args) -> None:
        show_debug = self.debug_checkbox.isChecked()
        if not show_debug or self.state.last_case is None:
            self.debug_output.setVisible(False)
            self.debug_output.clear()
            return

        payload = self.state.last_case.model_dump()
        self.debug_output.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        self.debug_output.setVisible(True)

    def _set_busy(self, busy: bool) -> None:
        self.generate_button.setEnabled((not busy) and self.consent_checkbox.isChecked())
        if busy:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        else:
            while QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()

    def _on_export_json_clicked(self, checked: bool = False) -> None:
        _ = checked
        if self.state.last_case is None:
            return

        file_name = f"case_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path, _ = QFileDialog.getSaveFileName(self, "保存 JSON", file_name, "JSON (*.json)")
        if not path:
            return

        try:
            with open(path, "wb") as file:
                file.write(export_case_json(self.state.last_case))
            self.statusBar().showMessage(f"已导出 JSON：{path}", 5000)
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", f"JSON 导出失败：{exc}")

    def _on_export_pdf_clicked(self, checked: bool = False) -> None:
        _ = checked
        if self.state.last_case is None:
            return

        file_name = f"case_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        path, _ = QFileDialog.getSaveFileName(self, "保存 PDF", file_name, "PDF (*.pdf)")
        if not path:
            return

        try:
            with open(path, "wb") as file:
                file.write(export_case_pdf(self.state.last_case))
            self.statusBar().showMessage(f"已导出 PDF：{path}", 5000)
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", f"PDF 导出失败：{exc}")
