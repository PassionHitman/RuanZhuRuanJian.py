"""步骤1：环境检查。"""
from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.state_machine import Stage, state


class EnvCheckStep(QWidget):
    stage_completed = pyqtSignal(Stage)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("第一步：环境检查")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)

        desc = QLabel(
            "检查当前运行环境是否满足软著材料生成要求，包括 Python 版本、python-docx 库等。"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #7f8c8d; margin-bottom: 8px;")
        layout.addWidget(desc)

        # 输出目录设置
        dir_group = QGroupBox("输出目录")
        dir_layout = QVBoxLayout(dir_group)
        self._dir_label = QLabel(f"将在当前目录下创建：{state.work_dir}/")
        dir_layout.addWidget(self._dir_label)
        layout.addWidget(dir_group)

        # 检查结果
        result_group = QGroupBox("环境检查结果")
        result_layout = QVBoxLayout(result_group)
        self._result_text = QTextEdit()
        self._result_text.setReadOnly(True)
        self._result_text.setMaximumHeight(300)
        result_layout.addWidget(self._result_text)
        layout.addWidget(result_group)

        # DeepSeek API 状态
        api_group = QGroupBox("DeepSeek API 状态")
        api_layout = QVBoxLayout(api_group)
        self._api_label = QLabel("点击下方按钮检测 API 连接状态...")
        api_layout.addWidget(self._api_label)
        layout.addWidget(api_group)

        # 按钮
        self._check_btn = QPushButton("🔍 开始环境检查")
        self._check_btn.setMinimumHeight(36)
        self._check_btn.clicked.connect(self._run_check)
        layout.addWidget(self._check_btn)

        self._confirm_btn = QPushButton("✓ 确认环境，进入下一步")
        self._confirm_btn.setMinimumHeight(36)
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.clicked.connect(self._confirm)
        layout.addWidget(self._confirm_btn)

        layout.addStretch()

    def refresh(self) -> None:
        pass

    def _run_check(self) -> None:
        """执行环境检查。"""
        results: list[str] = []

        # 1. Python 版本
        import sys
        py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        results.append(f"✓ Python 版本：{py_version}")

        # 2. python-docx
        try:
            import docx
            results.append("✓ python-docx：已安装")
        except ImportError:
            results.append("✗ python-docx：未安装（运行 pip install python-docx）")

        # 3. openai (DeepSeek)
        try:
            import openai
            results.append("✓ openai SDK：已安装")
        except ImportError:
            results.append("✗ openai SDK：未安装（运行 pip install openai）")

        # 4. 输出目录
        state.work_dir.mkdir(parents=True, exist_ok=True)
        results.append(f"✓ 输出目录：{state.work_dir.resolve()}")

        # 5. DeepSeek API Key
        from core.config import get_api_key
        api_key = get_api_key()
        if api_key:
            results.append("✓ DeepSeek API Key：已配置")
            self._api_label.setText("API Key 已配置 ✓")
            self._api_label.setStyleSheet("color: #27ae60;")
        else:
            results.append("⚠ DeepSeek API Key：未配置（请在设置中输入）")
            self._api_label.setText("API Key 未配置，请在菜单栏「设置」中输入")
            self._api_label.setStyleSheet("color: #e67e22;")

        self._result_text.setPlainText("\n".join(results))
        state.env_check_ok = True
        self._confirm_btn.setEnabled(True)

    def _confirm(self) -> None:
        """确认环境并进入下一步。"""
        from core.runner import check_environment as run_env_check
        import json

        # 1. 运行环境检查脚本
        returncode, stdout, stderr = run_env_check(str(state.work_dir))

        # 2. 检查是否需要用户选择 DOCX 环境
        env_json_path = state.work_dir / "环境检查.json"
        if env_json_path.exists():
            env_data = json.loads(env_json_path.read_text(encoding="utf-8"))
            if env_data.get("requires_user_input"):
                # 用户需要选择：安装完整环境 or 兜底继续
                msg = QMessageBox(self)
                msg.setWindowTitle("DOCX 环境不完整")
                msg.setText(
                    "完整 DOCX OpenXML 环境（需要 .NET SDK）不可用。\n\n"
                    "• 安装完整环境：需要安装 .NET SDK 8.0+\n"
                    "• 兜底继续：使用 python-docx 基础方式生成 Word（推荐）\n\n"
                    "建议选择「兜底继续」，生成的 Word 文件同样可用，无需额外安装。"
                )
                btn_fallback = msg.addButton("兜底继续（推荐）", QMessageBox.ButtonRole.YesRole)
                btn_install = msg.addButton("安装完整环境", QMessageBox.ButtonRole.NoRole)
                msg.setDefaultButton(btn_fallback)
                msg.exec()

                if msg.clickedButton() == btn_fallback:
                    choice = "用户选择：使用基础 DOCX 兜底继续"
                else:
                    choice = "用户选择：安装完整环境"
                    QMessageBox.information(
                        self, "提示",
                        "请安装 .NET SDK 8.0+ 后重启本应用。\n"
                        "下载地址：https://dotnet.microsoft.com/download"
                    )
                    return

                # 记录环境确认，解除 analyze_project.py 的门禁
                from core.runner import confirm_stage
                confirm_stage(str(state.work_dir), "environment", choice)

        # 3. 允许继续
        self.stage_completed.emit(Stage.ENVIRONMENT)
