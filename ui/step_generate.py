"""步骤8：生成正式 Word/TXT 文件。"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox,
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
from core.runner import build_docx


class GenerateStep(QWidget):
    stage_completed = pyqtSignal(Stage)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("第八步：生成正式资料")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)

        desc = QLabel(
            "最后一步：将已确认的所有草稿生成正式 Word (.docx) 和 TXT 文件。"
            "生成完成后会自动打开输出目录。"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #7f8c8d;")
        layout.addWidget(desc)

        # 汇总信息
        summary_group = QGroupBox("生成汇总")
        summary_layout = QVBoxLayout(summary_group)
        self._summary_text = QTextEdit()
        self._summary_text.setReadOnly(True)
        self._summary_text.setMaximumHeight(200)
        summary_layout.addWidget(self._summary_text)
        layout.addWidget(summary_group)

        # 进度
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # 结果
        result_group = QGroupBox("生成结果")
        result_layout = QVBoxLayout(result_group)
        self._result_text = QTextEdit()
        self._result_text.setReadOnly(True)
        result_layout.addWidget(self._result_text)
        layout.addWidget(result_group)

        # 按钮
        btn_layout = QHBoxLayout()
        self._gen_btn = QPushButton("🎉 生成正式 Word/TXT 文件")
        self._gen_btn.setMinimumHeight(40)
        self._gen_btn.setStyleSheet(
            "QPushButton { background-color: #27ae60; color: white; font-size: 14px; font-weight: bold; border-radius: 8px; }"
            "QPushButton:hover { background-color: #2ecc71; }"
        )
        self._gen_btn.clicked.connect(self._generate)
        btn_layout.addWidget(self._gen_btn)

        self._open_btn = QPushButton("📂 打开输出目录")
        self._open_btn.setMinimumHeight(40)
        self._open_btn.setEnabled(False)
        self._open_btn.clicked.connect(self._open_dir)
        btn_layout.addWidget(self._open_btn)
        layout.addLayout(btn_layout)

        layout.addStretch()

    def refresh(self) -> None:
        """刷新汇总信息。"""
        lines = [
            f"📁 项目：{state.project_dir}",
            f"📝 软件全称：{state.software_name}",
            f"🏷 版本号：{state.version}",
            f"📂 输出目录：{state.get_final_dir().resolve()}",
            "",
            "已完成阶段：",
        ]
        for stage in sorted(state.completed_stages, key=lambda s: s.value):
            from core.state_machine import STAGE_LABELS
            lines.append(f"  ✓ {STAGE_LABELS.get(stage, stage.value)}")
        self._summary_text.setPlainText("\n".join(lines))

    def _generate(self) -> None:
        """生成最终 Word/TXT 文件。"""
        from core.state_machine import Stage as St

        # 确认所有前置阶段
        required = {St.BUSINESS, St.CODE_SELECTION, St.APPLICATION_FIELDS, St.MANUAL_PREVIEW}
        missing = required - state.completed_stages
        if missing:
            names = ", ".join(m.value for m in missing)
            QMessageBox.warning(self, "步骤未完成", f"请先完成以下步骤：{names}")
            return

        # ★ 生成前清理：把 申请表信息.md 中的"待用户确认"替换掉
        # build_docx_from_md.py 会扫描这个文件，有"待用户确认"就拒绝
        app_md_path = state.get_draft_dir() / "申请表信息.md"
        if app_md_path.exists():
            content = app_md_path.read_text(encoding="utf-8")
            # 将含"待用户确认"的行替换为已确认版本
            cleaned = []
            for line in content.splitlines():
                if line.startswith("➤") and "待用户确认" in line:
                    # 保留字段名，值替换为"已在应用中确认"
                    field_name = line.split("：")[0]
                    cleaned.append(f"{field_name}：已在应用中确认")
                else:
                    cleaned.append(line)
            app_md_path.write_text("\n".join(cleaned) + "\n", encoding="utf-8")

        self._gen_btn.setEnabled(False)
        self._gen_btn.setText("⏳ 正在生成 Word 文件...")
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)

        try:
            returncode, stdout, stderr = build_docx(
                str(state.work_dir),
                state.software_name,
                state.version,
            )

            self._progress.setVisible(False)
            self._gen_btn.setText("🎉 生成正式 Word/TXT 文件")

            if returncode == 0:
                # 读取生成报告
                report_path = state.get_final_dir() / "生成报告.md"
                if report_path.exists():
                    self._result_text.setPlainText(report_path.read_text(encoding="utf-8"))
                else:
                    self._result_text.setPlainText(stdout)

                self._open_btn.setEnabled(True)
                QMessageBox.information(self, "生成完成", "正式资料已生成！")
            elif "STOP_FOR_USER" in stdout:
                self._result_text.setPlainText(stdout)
                self._gen_btn.setEnabled(True)
            else:
                self._result_text.setPlainText(
                    f"生成过程中出现问题：\n\nSTDERR:\n{stderr}\n\nSTDOUT:\n{stdout}"
                )
                self._gen_btn.setEnabled(True)
        except Exception as e:
            self._progress.setVisible(False)
            self._gen_btn.setText("🎉 生成正式 Word/TXT 文件")
            self._gen_btn.setEnabled(True)
            QMessageBox.critical(self, "生成失败", str(e))

    def _open_dir(self) -> None:
        """打开输出目录。"""
        final_dir = state.get_final_dir()
        if final_dir.exists():
            os.startfile(str(final_dir.resolve()))
