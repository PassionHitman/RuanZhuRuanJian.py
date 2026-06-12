"""工作流状态机：管理 8 个阶段的进展和门禁。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Stage(Enum):
    ENVIRONMENT = "environment"
    PROJECT = "project"
    BUSINESS = "business"
    CODE_SELECTION = "code-selection"
    APPLICATION_FIELDS = "application-fields"
    SCREENSHOT = "screenshot"
    MANUAL_PREVIEW = "manual-preview"
    GENERATE = "generate"


STAGE_ORDER = list(Stage)
STAGE_LABELS: dict[Stage, str] = {
    Stage.ENVIRONMENT: "环境检查",
    Stage.PROJECT: "选择项目",
    Stage.BUSINESS: "业务理解",
    Stage.CODE_SELECTION: "代码选择",
    Stage.APPLICATION_FIELDS: "申请表信息",
    Stage.SCREENSHOT: "截图管理",
    Stage.MANUAL_PREVIEW: "操作手册预览",
    Stage.GENERATE: "生成资料",
}


@dataclass
class WorkflowState:
    """保存整个工作流的数据和进度。"""

    # 项目信息
    project_dir: Path | None = None
    software_name: str = ""
    version: str = "V1.0"

    # 输出目录（在分析项目后自动设置）
    work_dir: Path = Path("软件著作权申请资料")

    def setup_output_dir(self) -> Path:
        """根据项目名称和日期创建独立的输出子目录，防止覆盖旧项目。"""
        from datetime import date

        if self.software_name:
            safe_name = self.software_name.replace("/", "_").replace("\\", "_").replace(":", "_")[:30]
        else:
            safe_name = "未命名项目"
        date_str = date.today().strftime("%Y%m%d")
        sub_dir = f"{safe_name}_{date_str}"
        self.work_dir = Path("软件著作权申请资料") / sub_dir
        return self.work_dir

    # 阶段进度
    current_stage: Stage = Stage.ENVIRONMENT
    completed_stages: set[Stage] = field(default_factory=set)

    # 各阶段数据
    env_check_ok: bool = False
    env_has_docx_full: bool = False
    analysis: dict[str, Any] | None = None
    business_context: dict[str, Any] | None = None
    code_selection: dict[str, Any] | None = None
    code_manifest: dict[str, Any] | None = None
    app_fields: dict[str, str] = field(default_factory=dict)
    screenshot_method: str = ""
    manual_draft_ok: bool = False

    # AI 生成的中间结果
    ai_business_json: dict[str, Any] | None = None
    ai_code_selection_updates: list[dict[str, Any]] | None = None
    ai_manual_text: str = ""

    def complete_stage(self, stage: Stage) -> None:
        self.completed_stages.add(stage)
        self._advance()

    def can_proceed_to(self, stage: Stage) -> bool:
        """检查是否可以进入某个阶段（所有前面的阶段必须完成）。"""
        idx = STAGE_ORDER.index(stage)
        for prev_stage in STAGE_ORDER[:idx]:
            if prev_stage not in self.completed_stages:
                return False
        return True

    def _advance(self) -> None:
        """自动寻找下一个未完成的阶段。"""
        for stage in STAGE_ORDER:
            if stage not in self.completed_stages:
                self.current_stage = stage
                return

    def get_draft_dir(self) -> Path:
        return self.work_dir / "草稿"

    def get_final_dir(self) -> Path:
        return self.work_dir / "正式资料"

    def get_analysis_dir(self) -> Path:
        return self.work_dir / "analysis"

    def get_screenshot_dir(self) -> Path:
        return self.work_dir / "截图"


# 全局状态
state = WorkflowState()
