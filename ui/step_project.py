"""步骤2：项目选择。"""
from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.state_machine import Stage, state
from core.runner import analyze_project


class ProjectStep(QWidget):
    stage_completed = pyqtSignal(Stage)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("第二步：选择项目")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)

        desc = QLabel(
            "选择要生成软著材料的项目目录。程序会自动扫描分析项目结构、代码文件和框架。"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #7f8c8d; margin-bottom: 8px;")
        layout.addWidget(desc)

        # 路径选择
        path_group = QGroupBox("项目路径")
        path_layout = QVBoxLayout(path_group)
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("点击浏览选择项目目录，或手动输入路径...")
        path_layout.addWidget(self._path_edit)

        browse_layout = QVBoxLayout()
        self._browse_btn = QPushButton("📁 浏览文件夹")
        self._browse_btn.clicked.connect(self._browse)
        browse_layout.addWidget(self._browse_btn)
        path_layout.addLayout(browse_layout)
        layout.addWidget(path_group)

        # 自动扫描结果
        scan_group = QGroupBox("自动扫描（当前目录）")
        scan_layout = QVBoxLayout(scan_group)
        self._scan_list = QListWidget()
        self._scan_list.itemDoubleClicked.connect(self._on_select_scan)
        scan_layout.addWidget(self._scan_list)
        layout.addWidget(scan_group)

        # 分析结果
        result_group = QGroupBox("项目分析结果")
        result_layout = QVBoxLayout(result_group)
        self._result_label = QLabel("选择项目后将自动分析...")
        self._result_label.setWordWrap(True)
        result_layout.addWidget(self._result_label)
        layout.addWidget(result_group)

        # 按钮
        self._analyze_btn = QPushButton("🔍 分析项目")
        self._analyze_btn.setMinimumHeight(36)
        self._analyze_btn.clicked.connect(self._analyze)
        layout.addWidget(self._analyze_btn)

        self._confirm_btn = QPushButton("✓ 确认项目，进入下一步")
        self._confirm_btn.setMinimumHeight(36)
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.clicked.connect(self._confirm)
        layout.addWidget(self._confirm_btn)

        layout.addStretch()

    def refresh(self) -> None:
        self._scan_current_dir()

    def _scan_current_dir(self) -> None:
        """扫描当前目录，找可能的项目根目录。"""
        self._scan_list.clear()
        current = Path.cwd()
        # 检查当前目录
        if self._has_project_files(current):
            item = QListWidgetItem(f"📁 {current.name} （当前目录）")
            item.setData(Qt.ItemDataRole.UserRole, str(current))
            self._scan_list.addItem(item)
        # 检查子目录
        try:
            for entry in sorted(current.iterdir()):
                if entry.is_dir() and not entry.name.startswith("."):
                    if self._has_project_files(entry):
                        item = QListWidgetItem(f"📁 {entry.name}")
                        item.setData(Qt.ItemDataRole.UserRole, str(entry))
                        self._scan_list.addItem(item)
        except PermissionError:
            pass

    @staticmethod
    def _has_project_files(path: Path) -> bool:
        """检查是否是项目目录。"""
        indicators = [
            "package.json", "pyproject.toml", "Cargo.toml",
            "go.mod", "pom.xml", "build.gradle", "composer.json",
            "src/", "app/", "index.html", "README.md",
        ]
        for indicator in indicators:
            if indicator.endswith("/"):
                if (path / indicator.rstrip("/")).is_dir():
                    return True
            elif (path / indicator).exists():
                return True
        return False

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择项目目录")
        if path:
            self._path_edit.setText(path)
            state.project_dir = Path(path)

    def _on_select_scan(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self._path_edit.setText(path)
            state.project_dir = Path(path)

    def _analyze(self) -> None:
        """运行项目分析。"""
        import json, tempfile

        project_path = self._path_edit.text().strip()
        if not project_path:
            QMessageBox.warning(self, "提示", "请先选择项目目录")
            return

        project_dir = Path(project_path)
        if not project_dir.exists():
            QMessageBox.warning(self, "提示", f"目录不存在：{project_path}")
            return

        state.project_dir = project_dir

        # 1. 先跑项目分析（写到临时目录，因为还不知道最终输出目录）
        temp_dir = Path(tempfile.mkdtemp(prefix="sc_analysis_"))
        temp_out = temp_dir / "project.json"

        returncode, stdout, stderr = analyze_project(
            str(project_dir), str(temp_out)
        )

        if returncode != 0:
            QMessageBox.critical(self, "分析失败", stderr or stdout)
            return

        # 2. 读取分析结果，获取软件名称
        state.analysis = json.loads(temp_out.read_text(encoding="utf-8"))
        state.software_name = (
            state.analysis.get("software_name_candidate")
            or state.analysis.get("project_name", "")
            or project_dir.name
        )
        pkg = state.analysis.get("package", {})
        state.version = pkg.get("version", "V1.0") if pkg else "V1.0"
        if state.version and not state.version.startswith("V"):
            state.version = f"V{state.version}"

        # 3. 根据项目名+日期创建独立子目录，防止覆盖旧项目
        state.setup_output_dir()
        analysis_dir = state.get_analysis_dir()
        analysis_dir.mkdir(parents=True, exist_ok=True)
        out_path = analysis_dir / "project.json"

        # 4. 写入 project.json 到新子目录
        out_path.write_text(
            json.dumps(state.analysis, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 清理临时目录
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

        # 5. 显示摘要
        a = state.analysis
        lines = [
            f"✓ 项目名称：{a.get('project_name', '')}",
            f"✓ 软件名称：{state.software_name}",
            f"✓ 版本号：{state.version}",
            f"✓ 输出目录：{state.work_dir}",
            f"✓ 框架：{', '.join(a.get('frameworks', [])) or '未识别'}",
            f"✓ 语言：{a.get('language', '')}",
            f"✓ 源码文件数：{a.get('source', {}).get('file_count', 0)}",
            f"✓ 源程序行数：{a.get('source', {}).get('line_count', 0)}",
            f"✓ 路由数：{len(a.get('routes', []))}",
        ]
        self._result_label.setText("\n".join(lines))

        self._confirm_btn.setEnabled(True)

    def _confirm(self) -> None:
        if not state.analysis:
            QMessageBox.warning(self, "提示", "请先分析项目")
            return
        self.stage_completed.emit(Stage.PROJECT)
