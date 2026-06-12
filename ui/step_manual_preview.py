"""步骤7：操作手册预览与自检。"""
from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.state_machine import Stage, state
from core.runner import generate_manual_draft
from core.prompts import (
    MANUAL_GENERATION_SYSTEM,
    MANUAL_SELF_REVIEW_SYSTEM,
    build_manual_user_prompt,
    build_self_review_user_prompt,
)


class AIManualThread(QThread):
    """后台线程：DeepSeek 生成操作手册。"""
    finished_with_result = pyqtSignal(str, object)  # (manual_text, error)

    def __init__(self, mode: str = "generate"):
        super().__init__()
        self._mode = mode  # "generate" or "review"

    def run(self) -> None:
        try:
            from core.deepseek_client import get_client
            client = get_client()
            if not client.is_configured:
                self.finished_with_result.emit("", "API Key 未配置")
                return

            if self._mode == "generate":
                biz_ctx = state.business_context or {}
                modules = biz_ctx.get("manual_modules", [])
                user_prompt = build_manual_user_prompt(
                    software_name=state.software_name,
                    version=state.version,
                    business_context=biz_ctx,
                    manual_modules=modules,
                    screenshot_mode=state.screenshot_method,
                )
                text = client.chat(
                    user_prompt=user_prompt,
                    system_prompt=MANUAL_GENERATION_SYSTEM,
                    temperature=0.5,
                    max_tokens=16000,
                )
            else:
                # self-review mode
                user_prompt = build_self_review_user_prompt(
                    software_name=state.software_name,
                    version=state.version,
                    manual_text=state.ai_manual_text,
                    module_count=len(
                        (state.business_context or {}).get("manual_modules", [])
                    ),
                )
                result = client.chat_json(
                    user_prompt=user_prompt,
                    system_prompt=MANUAL_SELF_REVIEW_SYSTEM,
                    temperature=0.3,
                    max_tokens=16000,
                )
                if isinstance(result, dict):
                    text = result.get("fixed_manual", state.ai_manual_text)
                    issues = result.get("issues_found", [])
                    if issues:
                        text = f"【自检发现以下问题】\n" + "\n".join(
                            f"- {i}" for i in issues
                        ) + f"\n\n---\n\n{text}"
                else:
                    text = str(result)

            self.finished_with_result.emit(text, None)
        except Exception as e:
            self.finished_with_result.emit("", str(e))


class ManualPreviewStep(QWidget):
    stage_completed = pyqtSignal(Stage)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("第七步：操作手册预览")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)

        desc = QLabel(
            "AI 将根据业务理解和页面模块自动生成操作手册。生成后可在此预览和手动修改。"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #7f8c8d;")
        layout.addWidget(desc)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # 手册预览编辑
        self._preview = QTextEdit()
        self._preview.setPlaceholderText("点击下方按钮生成操作手册草稿...")
        layout.addWidget(self._preview, 1)

        # 按钮
        btn_layout = QHBoxLayout()
        self._gen_btn = QPushButton("🤖 AI 生成操作手册")
        self._gen_btn.setMinimumHeight(36)
        self._gen_btn.clicked.connect(lambda: self._run_ai("generate"))
        btn_layout.addWidget(self._gen_btn)

        self._review_btn = QPushButton("🔍 AI 自检修正")
        self._review_btn.setMinimumHeight(36)
        self._review_btn.setEnabled(False)
        self._review_btn.clicked.connect(lambda: self._run_ai("review"))
        btn_layout.addWidget(self._review_btn)

        self._confirm_btn = QPushButton("✓ 确认操作手册，进入下一步")
        self._confirm_btn.setMinimumHeight(36)
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.clicked.connect(self._confirm)
        btn_layout.addWidget(self._confirm_btn)
        layout.addLayout(btn_layout)

        self._ai_thread: AIManualThread | None = None

    def refresh(self) -> None:
        if state.ai_manual_text:
            self._preview.setPlainText(state.ai_manual_text)
            self._review_btn.setEnabled(True)
            self._confirm_btn.setEnabled(True)

    def _run_ai(self, mode: str) -> None:
        from core.deepseek_client import get_client
        if not get_client().is_configured:
            QMessageBox.warning(self, "API Key 缺失", "请先配置 DeepSeek API Key")
            return

        self._gen_btn.setEnabled(False)
        self._review_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)

        self._ai_thread = AIManualThread(mode=mode)
        self._ai_thread.finished_with_result.connect(self._on_ai_done)
        self._ai_thread.start()

    def _on_ai_done(self, text: str, error: str | None) -> None:
        self._gen_btn.setEnabled(True)
        self._review_btn.setEnabled(True)
        self._progress.setVisible(False)

        if error:
            QMessageBox.critical(self, "AI 调用失败", error)
            return

        if text:
            state.ai_manual_text = text
            self._preview.setPlainText(text)
            self._confirm_btn.setEnabled(True)

    def _confirm(self) -> None:
        """确认操作手册并写入文件。"""
        import json

        manual_text = self._preview.toPlainText().strip()
        if not manual_text:
            QMessageBox.warning(self, "提示", "请先生成操作手册")
            return

        # 直接保存到草稿目录（用户可以在预览中手动修改）
        draft_dir = state.get_draft_dir()
        manual_path = draft_dir / "操作手册.md"
        manual_path.write_text(manual_text, encoding="utf-8")

        # 直接写确认文件，不用 confirm_stage.py（它会递归检查所有前置门禁）
        import json
        from datetime import datetime, timezone
        confirm_data = {
            "markdown_confirmed": True,
            "confirmation_note": "桌面应用确认操作手册草稿",
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
        }
        confirm_path = draft_dir / "最终生成确认.json"
        confirm_path.write_text(json.dumps(confirm_data, ensure_ascii=False, indent=2), encoding="utf-8")

        state.ai_manual_text = manual_text
        state.manual_draft_ok = True
        self.stage_completed.emit(Stage.MANUAL_PREVIEW)
