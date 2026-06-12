"""Python 脚本调用器：封装对 scripts/ 目录下脚本的调用。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _run_script(script_name: str, args: list[str]) -> tuple[int, str, str]:
    """运行指定脚本并返回 (returncode, stdout, stderr)。"""
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        return 1, "", f"脚本不存在: {script_path}"

    cmd = [sys.executable, str(script_path)] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(Path.cwd()),
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 99, "", "脚本执行超时"
    except Exception as e:
        return 99, "", str(e)


def check_environment(out_dir: str) -> tuple[int, str, str]:
    """运行环境检查脚本。"""
    return _run_script("check_environment.py", ["--out-dir", out_dir])


def analyze_project(project_dir: str, out_path: str) -> tuple[int, str, str]:
    """运行项目分析脚本。"""
    return _run_script("analyze_project.py", [
        "--project", project_dir,
        "--out", out_path,
    ])


def generate_business_evidence(
    project_dir: str,
    analysis_path: str,
    software_name: str,
    out_dir: str,
) -> tuple[int, str, str]:
    """收集业务理解证据（不写入模型判断）。"""
    return _run_script("generate_business_context.py", [
        "--project", project_dir,
        "--analysis", analysis_path,
        "--software-name", software_name,
        "--out-dir", out_dir,
    ])


def generate_business_context(
    project_dir: str,
    analysis_path: str,
    software_name: str,
    out_dir: str,
    model_context_path: str,
) -> tuple[int, str, str]:
    """写入模型判断后的业务理解。"""
    return _run_script("generate_business_context.py", [
        "--project", project_dir,
        "--analysis", analysis_path,
        "--software-name", software_name,
        "--out-dir", out_dir,
        "--model-context", model_context_path,
    ])


def propose_code_selection(
    project_dir: str,
    out_dir: str,
) -> tuple[int, str, str]:
    """生成代码候选清单。"""
    return _run_script("propose_code_selection.py", [
        "--project", project_dir,
        "--out-dir", out_dir,
    ])


def extract_code_material(
    project_dir: str,
    analysis_path: str,
    selection_path: str,
    software_name: str,
    version: str,
    out_dir: str,
) -> tuple[int, str, str]:
    """抽取代码材料。"""
    return _run_script("extract_code_material.py", [
        "--project", project_dir,
        "--analysis", analysis_path,
        "--selection", selection_path,
        "--software-name", software_name,
        "--version", version,
        "--out-dir", out_dir,
    ])


def generate_application_info(
    analysis_path: str,
    code_manifest_path: str,
    software_name: str,
    version: str,
    out_dir: str,
    business_context_path: str = "",
    answers_path: str = "",
) -> tuple[int, str, str]:
    """生成申请表信息草稿。"""
    args = [
        "--analysis", analysis_path,
        "--code-manifest", code_manifest_path,
        "--software-name", software_name,
        "--version", version,
        "--out-dir", out_dir,
    ]
    if business_context_path:
        args += ["--business-context", business_context_path]
    if answers_path:
        args += ["--answers", answers_path]
    return _run_script("generate_application_info.py", args)


def generate_manual_draft(
    analysis_path: str,
    software_name: str,
    version: str,
    out_dir: str,
    business_context_path: str = "",
) -> tuple[int, str, str]:
    """生成操作手册草稿。"""
    args = [
        "--analysis", analysis_path,
        "--software-name", software_name,
        "--version", version,
        "--out-dir", out_dir,
    ]
    if business_context_path:
        args += ["--business-context", business_context_path]
    return _run_script("generate_manual_draft.py", args)


def build_docx(
    work_dir: str,
    software_name: str,
    version: str,
) -> tuple[int, str, str]:
    """生成正式 Word/TXT 文件。"""
    return _run_script("build_docx_from_md.py", [
        "--workdir", work_dir,
        "--software-name", software_name,
        "--version", version,
    ])


def confirm_stage(work_dir: str, stage: str, note: str) -> tuple[int, str, str]:
    """记录阶段确认门禁。"""
    return _run_script("confirm_stage.py", [
        "--workdir", work_dir,
        "--stage", stage,
        "--note", note,
    ])
