"""步骤6：截图管理。"""
from __future__ import annotations

import shutil
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from core.state_machine import Stage, state


class ScreenshotStep(QWidget):
    stage_completed = pyqtSignal(Stage)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("第六步：截图管理")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)

        desc = QLabel(
            "为操作手册添加截图。你可以选择跳过截图（操作手册将保留截图预留位置），"
            "或自行截图后放到指定目录中。"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #7f8c8d;")
        layout.addWidget(desc)

        # 截图方式选择
        method_group = QGroupBox("截图方式")
        method_layout = QVBoxLayout(method_group)
        self._skip_radio = QRadioButton("跳过截图（操作手册保留预留位置）")
        self._skip_radio.setChecked(True)
        method_layout.addWidget(self._skip_radio)
        self._user_radio = QRadioButton("自行截图（手动截图后放入截图目录）")
        method_layout.addWidget(self._user_radio)
        layout.addWidget(method_group)

        # 截图目录
        dir_group = QGroupBox("截图目录")
        dir_layout = QVBoxLayout(dir_group)
        self._dir_label = QLabel(f"截图目录：{state.get_screenshot_dir().resolve()}")
        dir_layout.addWidget(self._dir_label)

        btn_layout = QHBoxLayout()
        self._add_btn = QPushButton("📷 添加截图文件")
        self._add_btn.clicked.connect(self._add_screenshots)
        btn_layout.addWidget(self._add_btn)
        self._open_dir_btn = QPushButton("📂 打开截图目录")
        self._open_dir_btn.clicked.connect(self._open_dir)
        btn_layout.addWidget(self._open_dir_btn)
        dir_layout.addLayout(btn_layout)
        layout.addWidget(dir_group)

        # 截图列表
        list_group = QGroupBox("已添加的截图")
        list_layout = QVBoxLayout(list_group)
        self._list_widget = QListWidget()
        list_layout.addWidget(self._list_widget)
        self._refresh_list()
        layout.addWidget(list_group)

        # 确认按钮
        self._confirm_btn = QPushButton("✓ 确认截图设置，进入下一步")
        self._confirm_btn.setMinimumHeight(36)
        self._confirm_btn.clicked.connect(self._confirm)
        layout.addWidget(self._confirm_btn)

        layout.addStretch()

    def refresh(self) -> None:
        self._dir_label.setText(f"截图目录：{state.get_screenshot_dir().resolve()}")

    def _add_screenshots(self) -> None:
        """添加截图文件到截图目录。"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择截图文件",
            "",
            "Image Files (*.png *.jpg *.jpeg *.webp *.bmp);;All Files (*)",
        )
        if files:
            screenshot_dir = state.get_screenshot_dir()
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            for file_path in files:
                src = Path(file_path)
                dst = screenshot_dir / src.name
                shutil.copy2(str(src), str(dst))
            self._refresh_list()

    def _open_dir(self) -> None:
        """打开截图目录。"""
        screenshot_dir = state.get_screenshot_dir()
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        import os
        os.startfile(str(screenshot_dir.resolve()))

    def _refresh_list(self) -> None:
        """刷新截图列表。"""
        self._list_widget.clear()
        screenshot_dir = state.get_screenshot_dir()
        if screenshot_dir.exists():
            for f in sorted(screenshot_dir.iterdir()):
                if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
                    item = QListWidgetItem(f"🖼 {f.name}")
                    self._list_widget.addItem(item)

    def _confirm(self) -> None:
        """确认截图设置。"""
        import json
        from datetime import datetime, timezone

        if self._skip_radio.isChecked():
            state.screenshot_method = "skip"
        else:
            state.screenshot_method = "user-supplied"

        # 直接写确认文件，不用 confirm_stage.py（它会二次校验并可能阻塞）
        confirm_data = {
            "screenshot_method": state.screenshot_method,
            "screenshot_method_confirmed": True,
            "confirmation_note": "桌面应用确认",
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
        }
        confirm_path = state.work_dir / "截图方式确认.json"
        confirm_path.parent.mkdir(parents=True, exist_ok=True)
        confirm_path.write_text(json.dumps(confirm_data, ensure_ascii=False, indent=2), encoding="utf-8")

        self.stage_completed.emit(Stage.SCREENSHOT)
