"""步骤3：业务理解确认。"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.state_machine import Stage, state
from core.runner import generate_business_evidence, generate_business_context
from core.prompts import (
    BUSINESS_UNDERSTANDING_SYSTEM,
    build_business_user_prompt,
)


class AIBusinessThread(QThread):
    """后台线程调用 DeepSeek API 生成业务理解。"""
    finished_with_result = pyqtSignal(object, object)  # (result_dict, error_str)

    def run(self) -> None:
        try:
            from core.deepseek_client import get_client

            client = get_client()
            if not client.is_configured:
                self.finished_with_result.emit(None, "DeepSeek API Key 未配置")
                return

            analysis = state.analysis or {}
            routes = analysis.get("routes", [])
            categorized = analysis.get("source", {}).get("categorized_files", {})

            user_prompt = build_business_user_prompt(
                software_name=state.software_name,
                project_analysis=analysis,
                readme_excerpt=analysis.get("readme_excerpt", ""),
                routes=routes,
                entry_files=categorized.get("entry", []),
                page_files=categorized.get("page", []),
                component_files=categorized.get("component", []),
            )

            result = client.chat_json(
                user_prompt=user_prompt,
                system_prompt=BUSINESS_UNDERSTANDING_SYSTEM,
                temperature=0.3,
                max_tokens=16000,
            )
            self.finished_with_result.emit(result, None)
        except Exception as e:
            self.finished_with_result.emit(None, str(e))


class BusinessStep(QWidget):
    stage_completed = pyqtSignal(Stage)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("第三步：业务理解")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)

        desc = QLabel(
            "AI 将分析项目代码和文档，判断软件所属行业、目标用户、核心功能和操作流程。"
            "生成后请仔细确认并修改。"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #7f8c8d;")
        layout.addWidget(desc)

        # 软件名称和版本
        info_group = QGroupBox("基本信息")
        info_layout = QVBoxLayout(info_group)
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("软件全称："))
        self._name_edit = QLineEdit(state.software_name)
        self._name_edit.textChanged.connect(lambda t: setattr(state, "software_name", t))
        name_layout.addWidget(self._name_edit)
        info_layout.addLayout(name_layout)

        ver_layout = QHBoxLayout()
        ver_layout.addWidget(QLabel("版本号："))
        self._ver_edit = QLineEdit(state.version)
        self._ver_edit.textChanged.connect(lambda t: setattr(state, "version", t))
        ver_layout.addWidget(self._ver_edit)
        info_layout.addLayout(ver_layout)
        layout.addWidget(info_group)

        # 进度条
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # 结果预览
        preview_group = QGroupBox("业务理解预览（AI 生成后可在此编辑）")
        preview_layout = QVBoxLayout(preview_group)
        self._preview_text = QTextEdit()
        self._preview_text.setPlaceholderText('点击「生成业务理解」按钮，AI 将分析项目...')
        preview_layout.addWidget(self._preview_text)
        layout.addWidget(preview_group)

        # 按钮
        btn_layout = QHBoxLayout()
        self._gen_btn = QPushButton("🤖 AI 生成业务理解")
        self._gen_btn.setMinimumHeight(36)
        self._gen_btn.clicked.connect(self._generate)
        btn_layout.addWidget(self._gen_btn)

        self._confirm_btn = QPushButton("✓ 确认业务理解，进入下一步")
        self._confirm_btn.setMinimumHeight(36)
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.clicked.connect(self._confirm)
        btn_layout.addWidget(self._confirm_btn)
        layout.addLayout(btn_layout)

        layout.addStretch()

        self._ai_thread: AIBusinessThread | None = None

    def refresh(self) -> None:
        self._name_edit.setText(state.software_name)
        self._ver_edit.setText(state.version)

    def _generate(self) -> None:
        """调用 DeepSeek API 生成业务理解。"""
        if not state.analysis:
            QMessageBox.warning(self, "提示", "请先在第二步分析项目")
            return

        from core.deepseek_client import get_client
        if not get_client().is_configured:
            QMessageBox.warning(
                self, "API Key 缺失",
                "请先配置 DeepSeek API Key。\n\n"
                "通过菜单栏「设置」→「API 配置」输入你的 DeepSeek API Key。\n"
                "可前往 https://platform.deepseek.com 获取。"
            )
            return

        self._gen_btn.setEnabled(False)
        self._gen_btn.setText("⏳ AI 正在分析项目...")
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)  # 动画模式

        # 1. 先生成业务理解证据
        draft_dir = state.get_draft_dir()
        draft_dir.mkdir(parents=True, exist_ok=True)
        analysis_path = state.get_analysis_dir() / "project.json"

        returncode, stdout, stderr = generate_business_evidence(
            str(state.project_dir),
            str(analysis_path),
            state.software_name,
            str(draft_dir),
        )

        if returncode != 0:
            self._gen_btn.setEnabled(True)
            self._gen_btn.setText("🤖 AI 生成业务理解")
            self._progress.setVisible(False)
            QMessageBox.critical(self, "证据收集失败", stderr)
            return

        # 2. 调用 DeepSeek
        self._ai_thread = AIBusinessThread()
        self._ai_thread.finished_with_result.connect(self._on_ai_done)
        self._ai_thread.start()

    def _on_ai_done(self, result: object, error: str | None) -> None:
        """AI 分析完成。"""
        self._gen_btn.setEnabled(True)
        self._gen_btn.setText("🤖 AI 生成业务理解")
        self._progress.setVisible(False)

        if error:
            QMessageBox.critical(self, "AI 调用失败", error)
            return

        if not isinstance(result, dict):
            QMessageBox.critical(self, "AI 返回格式错误", "请重试")
            return

        state.ai_business_json = result
        # 显示预览
        preview_text = json.dumps(result, ensure_ascii=False, indent=2)
        self._preview_text.setPlainText(preview_text)
        self._confirm_btn.setEnabled(True)

    def _confirm(self) -> None:
        """确认业务理解，写入文件。"""
        if not state.ai_business_json:
            QMessageBox.warning(self, "提示", "请先生成业务理解")
            return

        draft_dir = state.get_draft_dir()
        analysis_path = state.get_analysis_dir() / "project.json"

        # 尝试从编辑器中读取用户修改后的 JSON
        try:
            edited_text = self._preview_text.toPlainText().strip()
            if edited_text:
                state.ai_business_json = json.loads(edited_text)
        except json.JSONDecodeError:
            QMessageBox.warning(self, "JSON 格式错误", "预览内容不是有效的 JSON，请检查后重试")
            return

        # 写入临时 JSON 供脚本读取
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(state.ai_business_json, tmp, ensure_ascii=False, indent=2)
            tmp_path = tmp.name

        try:
            returncode, stdout, stderr = generate_business_context(
                str(state.project_dir),
                str(analysis_path),
                state.software_name,
                str(draft_dir),
                tmp_path,
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        if returncode != 0:
            # STOP_FOR_USER 是正常输出，不是错误
            if "STOP_FOR_USER" not in stdout:
                QMessageBox.critical(self, "写入失败", stderr or stdout)
                return

        # ★ 解除业务理解门禁：把 user_confirmed 设为 true
        # 后续脚本（generate_application_info 等）会检查这个字段
        from core.runner import confirm_stage
        confirm_stage(str(state.work_dir), "business", "用户在桌面应用中确认业务理解")

        # 手动更新 JSON 文件中的 user_confirmed（confirm_stage.py 写的是独立文件）
        biz_json_path = draft_dir / "业务理解.json"
        if biz_json_path.exists():
            biz_data = json.loads(biz_json_path.read_text(encoding="utf-8"))
            biz_data["user_confirmed"] = True
            biz_json_path.write_text(json.dumps(biz_data, ensure_ascii=False, indent=2), encoding="utf-8")
            state.business_context = biz_data

        self.stage_completed.emit(Stage.BUSINESS)
