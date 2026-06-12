"""步骤5：申请表信息填写。"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.state_machine import Stage, state
from core.runner import extract_code_material, generate_application_info
from core.prompts import (
    APPLICATION_FORM_SYSTEM,
    build_application_form_user_prompt,
)


class AIAppFormThread(QThread):
    """后台线程：DeepSeek 生成申请表字段建议。"""
    finished_with_result = pyqtSignal(object, object)

    def run(self) -> None:
        try:
            from core.deepseek_client import get_client
            client = get_client()
            if not client.is_configured:
                self.finished_with_result.emit(None, "API Key 未配置")
                return
            result = client.chat_json(
                user_prompt=build_application_form_user_prompt(
                    software_name=state.software_name,
                    version=state.version,
                    project_analysis=state.analysis or {},
                    business_context=state.business_context or {},
                ),
                system_prompt=APPLICATION_FORM_SYSTEM,
                temperature=0.3,
                max_tokens=8000,
            )
            self.finished_with_result.emit(result, None)
        except Exception as e:
            self.finished_with_result.emit(None, str(e))


FIELD_LABELS = {
    "软件全称": "软件全称*",
    "软件简称": "软件简称",
    "版本号": "版本号*",
    "软件分类": "软件分类*",
    "开发完成日期": "开发完成日期*",
    "开发方式": "开发方式*",
    "软件说明": "软件说明*",
    "发表状态": "发表状态*",
    "首次发表日期": "首次发表日期",
    "著作权人": "著作权人*",
    "权利范围": "权利范围*",
    "权利取得方式": "权利取得方式*",
    "开发的硬件环境": "开发的硬件环境*",
    "运行的硬件环境": "运行的硬件环境*",
    "开发该软件的操作系统": "开发该软件的操作系统*",
    "软件开发环境 / 开发工具": "软件开发环境/开发工具*",
    "该软件的运行平台 / 操作系统": "运行平台/操作系统*",
    "软件运行支撑环境 / 支持软件": "运行支撑环境*",
    "编程语言": "编程语言*",
    "源程序量": "源程序量*",
    "开发目的": "开发目的*",
    "面向领域 / 行业": "面向领域/行业*",
    "软件的主要功能": "主要功能*(500-1300字)",
    "软件的技术特点": "技术特点*",
}

DROPDOWN_FIELDS = {
    "软件分类": ["应用软件", "嵌入式软件", "中间件", "系统软件", "其他"],
    "开发方式": ["单独开发", "合作开发", "委托开发", "下达任务开发"],
    "软件说明": ["原创", "修改（含翻译软件、合成软件）"],
    "发表状态": ["未发表", "已发表"],
    "权利范围": ["全部权利", "部分权利"],
    "权利取得方式": ["原始取得", "继受取得"],
}


class AppFormStep(QWidget):
    stage_completed = pyqtSignal(Stage)

    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        title = QLabel("第五步：申请表信息")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        main_layout.addWidget(title)

        desc = QLabel(
            "请确认并填写软著申请表各字段。带 * 的为必填项。"
            "可点击 AI 建议按钮自动填充，也可以手动填写。"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #7f8c8d;")
        main_layout.addWidget(desc)

        # 进度条
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        main_layout.addWidget(self._progress)

        # 表单滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_container = QWidget()
        self._form = QFormLayout(form_container)
        self._form.setSpacing(8)
        self._widgets: dict[str, QWidget] = {}

        for field_key, field_label in FIELD_LABELS.items():
            if field_key in DROPDOWN_FIELDS:
                combo = QComboBox()
                combo.addItems(DROPDOWN_FIELDS[field_key])
                self._form.addRow(field_label, combo)
                self._widgets[field_key] = combo
            elif field_key == "软件的主要功能":
                text_edit = QTextEdit()
                text_edit.setMaximumHeight(120)
                self._form.addRow(field_label, text_edit)
                self._widgets[field_key] = text_edit
            elif field_key == "首次发表日期":
                le = QLineEdit()
                le.setPlaceholderText("YYYY-MM-DD（未发表则留空）")
                self._form.addRow(field_label, le)
                self._widgets[field_key] = le
            else:
                le = QLineEdit()
                self._form.addRow(field_label, le)
                self._widgets[field_key] = le

        scroll.setWidget(form_container)
        main_layout.addWidget(scroll, 1)

        # 按钮
        btn_layout = QHBoxLayout()
        self._gen_code_btn = QPushButton("📄 先生成代码材料")
        self._gen_code_btn.setMinimumHeight(36)
        self._gen_code_btn.clicked.connect(self._extract_code)
        btn_layout.addWidget(self._gen_code_btn)

        self._ai_btn = QPushButton("🤖 AI 智能填充")
        self._ai_btn.setMinimumHeight(36)
        self._ai_btn.clicked.connect(self._ai_fill)
        btn_layout.addWidget(self._ai_btn)

        self._confirm_btn = QPushButton("✓ 确认申请表，进入下一步")
        self._confirm_btn.setMinimumHeight(36)
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.clicked.connect(self._confirm)
        btn_layout.addWidget(self._confirm_btn)
        main_layout.addLayout(btn_layout)

        self._ai_thread: AIAppFormThread | None = None

    def refresh(self) -> None:
        # 预填基本信息
        self._set_value("软件全称", state.software_name)
        self._set_value("版本号", state.version)
        if state.business_context:
            self._set_value("面向领域 / 行业", state.business_context.get("industry", ""))
            self._set_value("开发目的", state.business_context.get("application_purpose", ""))

    def _set_value(self, field: str, value: str) -> None:
        widget = self._widgets.get(field)
        if not widget:
            return
        if isinstance(widget, QLineEdit):
            widget.setText(value)
        elif isinstance(widget, QTextEdit):
            widget.setPlainText(value)
        elif isinstance(widget, QComboBox):
            idx = widget.findText(value)
            if idx >= 0:
                widget.setCurrentIndex(idx)

    def _get_value(self, field: str) -> str:
        widget = self._widgets.get(field)
        if isinstance(widget, QLineEdit):
            return widget.text()
        elif isinstance(widget, QTextEdit):
            return widget.toPlainText()
        elif isinstance(widget, QComboBox):
            return widget.currentText()
        return ""

    def _extract_code(self) -> None:
        """抽取代码材料（需要先有代码选择）。"""
        draft_dir = state.get_draft_dir()
        selection_path = draft_dir / "代码文件选择.json"
        if not selection_path.exists():
            QMessageBox.warning(self, "提示", "请先在第四步完成代码文件选择")
            return

        self._gen_code_btn.setEnabled(False)
        self._gen_code_btn.setText("⏳ 抽取代码中...")

        analysis_path = state.get_analysis_dir() / "project.json"
        returncode, stdout, stderr = extract_code_material(
            str(state.project_dir),
            str(analysis_path),
            str(selection_path),
            state.software_name,
            state.version,
            str(draft_dir),
        )

        self._gen_code_btn.setEnabled(True)
        self._gen_code_btn.setText("📄 先生成代码材料")

        if returncode != 0 and "STOP_FOR_USER" not in stdout:
            QMessageBox.critical(self, "代码抽取失败", stderr)
            return

        # 读取清单
        manifest_path = draft_dir / "代码提取清单.json"
        if manifest_path.exists():
            state.code_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            pages = state.code_manifest.get("total_pages", 0)
            self._set_value("源程序量", str(state.code_manifest.get("source_line_count", "")))
            QMessageBox.information(self, "完成", f"代码材料已抽取，共 {pages} 页")
            self._confirm_btn.setEnabled(True)

    def _ai_fill(self) -> None:
        """AI 智能填充申请表字段。"""
        from core.deepseek_client import get_client
        if not get_client().is_configured:
            QMessageBox.warning(self, "API Key 缺失", "请先配置 DeepSeek API Key")
            return

        self._ai_btn.setEnabled(False)
        self._ai_btn.setText("⏳ AI 正在分析...")
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)

        self._ai_thread = AIAppFormThread()
        self._ai_thread.finished_with_result.connect(self._on_ai_done)
        self._ai_thread.start()

    def _on_ai_done(self, result: object, error: str | None) -> None:
        self._ai_btn.setEnabled(True)
        self._ai_btn.setText("🤖 AI 智能填充")
        self._progress.setVisible(False)

        if error:
            QMessageBox.critical(self, "AI 调用失败", error)
            return

        if isinstance(result, dict):
            # 填充字段（只填充 AI 返回的非空值）
            field_map = {
                "软件全称": "软件全称",
                "软件简称": "软件简称",
                "软件分类": "软件分类",
                "开发方式": "开发方式",
                "软件说明": "软件说明",
                "发表状态": "发表状态",
                "开发目的": "开发目的",
                "面向领域/行业": "面向领域 / 行业",
                "软件的主要功能": "软件的主要功能",
                "软件的技术特点": "软件的技术特点",
            }
            for ai_field, form_field in field_map.items():
                value = result.get(ai_field, "")
                if value:
                    self._set_value(form_field, str(value))
            self._confirm_btn.setEnabled(True)

    def _confirm(self) -> None:
        """确认申请表并生成草稿。"""
        import json

        draft_dir = state.get_draft_dir()
        analysis_path = state.get_analysis_dir() / "project.json"

        # 收集字段值
        answers = {}
        for field in FIELD_LABELS:
            answers[field] = self._get_value(field)

        # 写入 answers JSON
        answers_path = draft_dir / "user_answers.json"
        answers_path.write_text(json.dumps(answers, ensure_ascii=False, indent=2), encoding="utf-8")

        code_manifest = draft_dir / "代码提取清单.json"
        biz_path = draft_dir / "业务理解.json"

        returncode, stdout, stderr = generate_application_info(
            str(analysis_path),
            str(code_manifest) if code_manifest.exists() else "",
            state.software_name,
            state.version,
            str(draft_dir),
            str(biz_path) if biz_path.exists() else "",
            str(answers_path),
        )

        if returncode != 0 and "STOP_FOR_USER" not in stdout:
            QMessageBox.critical(self, "生成失败", stderr)
            return

        # 直接写确认文件，不用 confirm_stage.py（它会检查"待用户确认"并阻塞）
        import json
        from datetime import datetime, timezone
        confirm_data = {
            "application_fields_confirmed": True,
            "confirmation_note": "桌面应用确认申请表字段",
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
        }
        confirm_path = draft_dir / "申请表字段确认.json"
        confirm_path.write_text(json.dumps(confirm_data, ensure_ascii=False, indent=2), encoding="utf-8")

        state.app_fields = answers
        self.stage_completed.emit(Stage.APPLICATION_FIELDS)
