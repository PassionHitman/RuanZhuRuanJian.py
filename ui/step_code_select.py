"""步骤4：代码文件选择。"""
from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.state_machine import Stage, state
from core.runner import propose_code_selection
from core.prompts import (
    CODE_SELECTION_SYSTEM,
    build_code_selection_user_prompt,
)


class AICodeSelectThread(QThread):
    """后台线程调用 DeepSeek API 选择代码文件。"""
    finished_with_result = pyqtSignal(object, object)

    def run(self) -> None:
        try:
            from core.deepseek_client import get_client

            client = get_client()
            if not client.is_configured:
                self.finished_with_result.emit(None, "DeepSeek API Key 未配置")
                return

            candidates = state.code_selection.get("files", []) if state.code_selection else []
            biz_ctx = state.business_context or {}

            user_prompt = build_code_selection_user_prompt(
                software_name=state.software_name,
                business_features=biz_ctx.get("business_features", []),
                candidates=candidates,
            )

            result = client.chat_json(
                user_prompt=user_prompt,
                system_prompt=CODE_SELECTION_SYSTEM,
                temperature=0.3,
                max_tokens=16000,
            )
            self.finished_with_result.emit(result, None)
        except Exception as e:
            self.finished_with_result.emit(None, str(e))


class CodeSelectStep(QWidget):
    stage_completed = pyqtSignal(Stage)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("第四步：代码文件选择")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)

        desc = QLabel(
            "选择需要提交的源代码文件。优先选择前端页面、入口、路由等能体现软件功能的文件。"
            "需至少选择满足 60 页（约 3000 行）的代码。"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #7f8c8d;")
        layout.addWidget(desc)

        # 统计
        self._stats_label = QLabel("尚未生成候选清单")
        layout.addWidget(self._stats_label)

        # 进度条
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # 文件列表（滚动区域）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._file_container = QWidget()
        self._file_layout = QVBoxLayout(self._file_container)
        self._file_layout.setSpacing(2)
        scroll.setWidget(self._file_container)
        layout.addWidget(scroll, 1)

        # 按钮
        btn_layout = QHBoxLayout()
        self._propose_btn = QPushButton("📋 生成候选清单")
        self._propose_btn.setMinimumHeight(36)
        self._propose_btn.clicked.connect(self._propose)
        btn_layout.addWidget(self._propose_btn)

        self._ai_select_btn = QPushButton("🤖 AI 智能选择")
        self._ai_select_btn.setMinimumHeight(36)
        self._ai_select_btn.clicked.connect(self._ai_select)
        btn_layout.addWidget(self._ai_select_btn)

        self._confirm_btn = QPushButton("✓ 确认选择，进入下一步")
        self._confirm_btn.setMinimumHeight(36)
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.clicked.connect(self._confirm)
        btn_layout.addWidget(self._confirm_btn)
        layout.addLayout(btn_layout)

        self._checkboxes: dict[str, QCheckBox] = {}
        self._ai_thread: AICodeSelectThread | None = None

    def refresh(self) -> None:
        if state.code_selection:
            self._render_files()

    def _propose(self) -> None:
        """生成候选文件清单。"""
        if not state.project_dir:
            QMessageBox.warning(self, "提示", "请先选择项目")
            return

        self._propose_btn.setEnabled(False)
        self._propose_btn.setText("⏳ 扫描中...")

        draft_dir = state.get_draft_dir()
        draft_dir.mkdir(parents=True, exist_ok=True)

        returncode, stdout, stderr = propose_code_selection(
            str(state.project_dir), str(draft_dir)
        )

        self._propose_btn.setEnabled(True)
        self._propose_btn.setText("📋 生成候选清单")

        # 读取生成的文件
        selection_path = draft_dir / "代码文件选择.json"
        if selection_path.exists():
            state.code_selection = json.loads(selection_path.read_text(encoding="utf-8"))
            self._render_files()
            self._confirm_btn.setEnabled(True)

    def _render_files(self) -> None:
        """渲染文件选择列表。"""
        # 清空
        for i in reversed(range(self._file_layout.count())):
            widget = self._file_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        self._checkboxes.clear()

        if not state.code_selection:
            return

        files = state.code_selection.get("files", [])
        selected_count = 0
        selected_lines = 0

        for item in files:
            path = item.get("path", "")
            line_count = item.get("line_count", 0)
            selected = item.get("selected", False)
            evidence = item.get("evidence", "")

            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(4, 4, 4, 4)

            cb = QCheckBox(f"{path}  ({line_count} 行) [{evidence}]")
            cb.setChecked(selected)
            cb.toggled.connect(lambda checked, p=path: self._on_toggle(p, checked))
            row_layout.addWidget(cb)
            self._checkboxes[path] = cb

            self._file_layout.addWidget(row)

            if selected:
                selected_count += 1
                selected_lines += line_count + 2  # +2 for marker line

        pages = (selected_lines + 49) // 50
        total_candidates = len(files)
        total_lines = sum(item.get("line_count", 0) for item in files)
        total_pages = (total_lines + 49) // 50

        self._stats_label.setText(
            f"已选 {selected_count} 个文件 ~{selected_lines} 行 ~{pages} 页 | "
            f"候选共 {total_candidates} 个文件 ~{total_lines} 行 ~{total_pages} 页 | "
            f"目标：≥60 页"
        )

    def _on_toggle(self, path: str, checked: bool) -> None:
        """切换文件选中状态。"""
        if not state.code_selection:
            return
        for item in state.code_selection.get("files", []):
            if item.get("path") == path:
                item["selected"] = checked
                if checked and not item.get("model_reason"):
                    item["model_reason"] = "用户手动选择"
                break
        # 更新统计
        selected = [item for item in state.code_selection.get("files", []) if item.get("selected")]
        lines = sum(item.get("line_count", 0) + 2 for item in selected)
        pages = (lines + 49) // 50
        self._stats_label.setText(
            f"已选 {len(selected)} 个文件 ~{lines} 行 ~{pages} 页"
        )

    def _ai_select(self) -> None:
        """AI 智能选择代码文件。"""
        if not state.code_selection:
            QMessageBox.warning(self, "提示", "请先生成候选清单")
            return

        from core.deepseek_client import get_client
        if not get_client().is_configured:
            QMessageBox.warning(self, "API Key 缺失", "请先配置 DeepSeek API Key")
            return

        self._ai_select_btn.setEnabled(False)
        self._ai_select_btn.setText("⏳ AI 正在分析选择...")
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)

        self._ai_thread = AICodeSelectThread()
        self._ai_thread.finished_with_result.connect(self._on_ai_done)
        self._ai_thread.start()

    def _on_ai_done(self, result: object, error: str | None) -> None:
        """AI 选择完成。"""
        self._ai_select_btn.setEnabled(True)
        self._ai_select_btn.setText("🤖 AI 智能选择")
        self._progress.setVisible(False)

        if error:
            QMessageBox.critical(self, "AI 调用失败", error)
            return

        if isinstance(result, dict) and "files" in result:
            # 更新选择
            ai_files = {f["path"]: f for f in result["files"] if f.get("selected")}
            for item in state.code_selection.get("files", []):
                path = item.get("path", "")
                if path in ai_files:
                    item["selected"] = True
                    item["model_reason"] = ai_files[path].get("model_reason", "AI 推荐")
                else:
                    item["selected"] = False
            self._render_files()

    def _confirm(self) -> None:
        """确认代码选择并写入文件。"""
        if not state.code_selection:
            QMessageBox.warning(self, "提示", "请先生成候选清单")
            return

        selected = [item for item in state.code_selection.get("files", []) if item.get("selected")]
        if not selected:
            QMessageBox.warning(self, "提示", "请至少选择一个代码文件")
            return

        # 更新 JSON（标记已确认）
        state.code_selection["user_confirmed"] = True

        draft_dir = state.get_draft_dir()
        selection_path = draft_dir / "代码文件选择.json"
        selection_path.write_text(
            json.dumps(state.code_selection, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        self.stage_completed.emit(Stage.CODE_SELECTION)
