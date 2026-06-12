"""主窗口：左侧步骤导航 + 右侧内容区。"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.state_machine import STAGE_LABELS, STAGE_ORDER, Stage, state
from ui.step_env import EnvCheckStep
from ui.step_project import ProjectStep
from ui.step_business import BusinessStep
from ui.step_code_select import CodeSelectStep
from ui.step_app_form import AppFormStep
from ui.step_screenshot import ScreenshotStep
from ui.step_manual_preview import ManualPreviewStep
from ui.step_generate import GenerateStep


class StepButton(QPushButton):
    """左侧步骤导航按钮。"""
    clicked_stage = pyqtSignal(Stage)

    def __init__(self, stage: Stage, parent=None):
        label = STAGE_LABELS[stage]
        super().__init__(f"  {label}", parent)
        self._stage = stage
        self.setCheckable(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(42)
        font = QFont()
        font.setPointSize(10)
        self.setFont(font)
        self.clicked.connect(lambda: self.clicked_stage.emit(stage))

    def set_completed(self, completed: bool) -> None:
        if completed:
            self.setText(f"  ✓ {STAGE_LABELS[self._stage]}")
            self.setStyleSheet("color: #27ae60;")
        else:
            self.setText(f"  {STAGE_LABELS[self._stage]}")
            self.setStyleSheet("")

    def set_current(self, current: bool) -> None:
        if current:
            self.setStyleSheet(
                "background-color: #3498db; color: white; font-weight: bold; border-radius: 6px;"
            )
        else:
            self.setStyleSheet("")


class MainWindow(QMainWindow):
    """主窗口。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("软著申请资料生成工具")
        self.setMinimumSize(1100, 750)
        self.resize(1200, 820)

        # 中央 Widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── 左侧导航栏 ──
        nav_widget = QWidget()
        nav_widget.setFixedWidth(200)
        nav_widget.setStyleSheet("background-color: #f5f6fa; border-right: 1px solid #ddd;")
        nav_layout = QVBoxLayout(nav_widget)
        nav_layout.setContentsMargins(10, 15, 10, 15)
        nav_layout.setSpacing(6)

        title_label = QLabel("📋 申请流程")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        nav_layout.addWidget(title_label)
        nav_layout.addSpacing(10)

        self._step_buttons: dict[Stage, StepButton] = {}
        self._step_widgets: dict[Stage, QWidget] = {}
        self._stacked = QStackedWidget()

        for i, stage in enumerate(STAGE_ORDER):
            btn = StepButton(stage)
            num_label = f"{i + 1}."
            btn.setText(f"  {num_label} {STAGE_LABELS[stage]}")
            btn.clicked_stage.connect(self._on_step_clicked)
            nav_layout.addWidget(btn)
            self._step_buttons[stage] = btn

        nav_layout.addStretch()
        main_layout.addWidget(nav_widget)

        # ── 右侧内容区 ──
        right_widget = QWidget()
        right_widget.setStyleSheet("background-color: #ffffff;")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(20, 15, 20, 15)

        # 步骤面板
        self._create_step_panels()
        right_layout.addWidget(self._stacked)

        # 底部按钮
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        self._prev_btn = QPushButton("← 上一步")
        self._prev_btn.setMinimumWidth(100)
        self._prev_btn.clicked.connect(self._go_prev)
        bottom_layout.addWidget(self._prev_btn)
        self._next_btn = QPushButton("下一步 →")
        self._next_btn.setMinimumWidth(100)
        self._next_btn.clicked.connect(self._go_next)
        bottom_layout.addWidget(self._next_btn)
        right_layout.addLayout(bottom_layout)

        main_layout.addWidget(right_widget, 1)

        # 初始化状态
        self._refresh_nav()
        self._stacked.setCurrentIndex(0)

    def _create_step_panels(self) -> None:
        """创建所有步骤面板并添加到 QStackedWidget。"""
        panels = [
            ("env", EnvCheckStep()),
            ("project", ProjectStep()),
            ("business", BusinessStep()),
            ("code_select", CodeSelectStep()),
            ("app_form", AppFormStep()),
            ("screenshot", ScreenshotStep()),
            ("manual_preview", ManualPreviewStep()),
            ("generate", GenerateStep()),
        ]
        for name, widget in panels:
            self._stacked.addWidget(widget)
            # 通过 name 查找 stage
            stage_map = {
                "env": Stage.ENVIRONMENT,
                "project": Stage.PROJECT,
                "business": Stage.BUSINESS,
                "code_select": Stage.CODE_SELECTION,
                "app_form": Stage.APPLICATION_FIELDS,
                "screenshot": Stage.SCREENSHOT,
                "manual_preview": Stage.MANUAL_PREVIEW,
                "generate": Stage.GENERATE,
            }
            self._step_widgets[stage_map[name]] = widget
            # 连接完成信号
            if hasattr(widget, "stage_completed"):
                widget.stage_completed.connect(self._on_stage_completed)

    def _refresh_nav(self) -> None:
        """刷新左侧步骤导航的样式。"""
        for stage, btn in self._step_buttons.items():
            btn.set_completed(stage in state.completed_stages)
            btn.set_current(stage == state.current_stage)

    def _on_step_clicked(self, stage: Stage) -> None:
        """点击左侧步骤按钮。"""
        if state.can_proceed_to(stage) or stage in state.completed_stages:
            state.current_stage = stage
            self._refresh_nav()
            idx = STAGE_ORDER.index(stage)
            self._stacked.setCurrentIndex(idx)
            # 刷新当前面板
            self._refresh_current_panel()

    def _on_stage_completed(self, stage: Stage) -> None:
        """某步骤完成时调用。"""
        state.complete_stage(stage)
        self._refresh_nav()
        # 自动跳转下一步
        next_idx = STAGE_ORDER.index(state.current_stage)
        self._stacked.setCurrentIndex(next_idx)
        self._refresh_current_panel()

    def _go_prev(self) -> None:
        idx = STAGE_ORDER.index(state.current_stage)
        if idx > 0:
            state.current_stage = STAGE_ORDER[idx - 1]
            self._refresh_nav()
            self._stacked.setCurrentIndex(idx - 1)
            self._refresh_current_panel()

    def _go_next(self) -> None:
        idx = STAGE_ORDER.index(state.current_stage)
        if idx < len(STAGE_ORDER) - 1 and state.can_proceed_to(
            STAGE_ORDER[idx + 1]
        ):
            state.current_stage = STAGE_ORDER[idx + 1]
            self._refresh_nav()
            self._stacked.setCurrentIndex(idx + 1)
            self._refresh_current_panel()

    def _refresh_current_panel(self) -> None:
        """刷新当前显示的面板。"""
        panel = self._step_widgets.get(state.current_stage)
        if panel and hasattr(panel, "refresh"):
            panel.refresh()
