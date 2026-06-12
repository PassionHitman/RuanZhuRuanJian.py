#!/usr/bin/env python3
"""软著申请资料生成工具 — 桌面应用入口。

将软著申请流程从 Claude Code Skill 改造为独立的 PyQt6 桌面应用，
使用 DeepSeek API 替代 Claude 完成 AI 分析任务。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QThread
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from core.config import load_config, save_config
from core.state_machine import state
from ui.main_window import MainWindow


class ApiConfigDialog(QDialog):
    """DeepSeek API 配置对话框。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("API 配置")
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        label = QLabel(
            "请输入你的 DeepSeek API Key。\n"
            "可前往 <a href='https://platform.deepseek.com'>platform.deepseek.com</a> 获取。"
        )
        label.setOpenExternalLinks(True)
        label.setWordWrap(True)
        layout.addWidget(label)

        form = QFormLayout()
        self._api_key_edit = QLineEdit()
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_edit.setPlaceholderText("sk-...")
        form.addRow("API Key：", self._api_key_edit)

        self._base_url_edit = QLineEdit("https://api.deepseek.com")
        form.addRow("API 地址：", self._base_url_edit)
        layout.addLayout(form)

        # 加载当前配置
        config = load_config()
        self._api_key_edit.setText(config.get("deepseek_api_key", ""))
        self._base_url_edit.setText(config.get("deepseek_base_url", "https://api.deepseek.com"))

        # 测试按钮
        test_btn = QPushButton("🔍 测试连接")
        test_btn.clicked.connect(self._test_connection)
        layout.addWidget(test_btn)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        # 保存/取消
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _test_connection(self) -> None:
        """测试 DeepSeek API 连接。"""
        api_key = self._api_key_edit.text().strip()
        if not api_key:
            self._status_label.setText("❌ 请输入 API Key")
            self._status_label.setStyleSheet("color: #e74c3c;")
            return

        self._status_label.setText("⏳ 正在测试连接...")
        self._status_label.setStyleSheet("color: #f39c12;")

        try:
            from openai import OpenAI
            client = OpenAI(
                base_url=self._base_url_edit.text().strip(),
                api_key=api_key,
            )
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": "你好，请回复'连接成功'"}],
                max_tokens=10,
            )
            reply = response.choices[0].message.content
            if "连接成功" in reply:
                self._status_label.setText("✓ 连接成功！")
                self._status_label.setStyleSheet("color: #27ae60;")
            else:
                self._status_label.setText(f"✓ 连接成功（回复：{reply}）")
                self._status_label.setStyleSheet("color: #27ae60;")
        except Exception as e:
            self._status_label.setText(f"❌ 连接失败：{str(e)[:200]}")
            self._status_label.setStyleSheet("color: #e74c3c;")

    def _save(self) -> None:
        """保存配置。"""
        api_key = self._api_key_edit.text().strip()
        if not api_key:
            QMessageBox.warning(self, "提示", "请输入 API Key")
            return

        config = load_config()
        config["deepseek_api_key"] = api_key
        config["deepseek_base_url"] = self._base_url_edit.text().strip()
        save_config(config)
        self.accept()


def main() -> None:
    """应用主入口。"""
    app = QApplication(sys.argv)
    app.setApplicationName("软著申请资料生成工具")
    app.setStyle("Fusion")

    # 检查首次运行
    config = load_config()
    if not config.get("deepseek_api_key"):
        dialog = ApiConfigDialog()
        if dialog.exec() == QDialog.DialogCode.Rejected:
            # 用户取消，仍可启动但功能受限
            pass

    # 创建主窗口
    window = MainWindow()

    # 菜单栏
    menubar = window.menuBar()
    settings_menu = menubar.addMenu("设置")
    api_action = QAction("API 配置", window)
    api_action.triggered.connect(lambda: ApiConfigDialog(window).exec())
    settings_menu.addAction(api_action)

    help_menu = menubar.addMenu("帮助")
    about_action = QAction("关于", window)
    about_action.triggered.connect(
        lambda: QMessageBox.about(
            window,
            "关于",
            "软著申请资料生成工具 v1.0\n\n"
            "基于开源项目 SoftwareCopyright-Skill 改造\n"
            "AI 引擎：DeepSeek API\n\n"
            "自动生成中国软件著作权申请所需的：\n"
            "• 申请表信息\n"
            "• 源代码文档（前30页/后30页）\n"
            "• 操作手册",
        )
    )
    help_menu.addAction(about_action)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
