# 软著申请资料生成工具

> 一款基于 PyQt6 + DeepSeek AI 的桌面应用，自动生成中国版权保护中心软件著作权登记所需的全部材料。

## ✨ 核心功能

- **AI 驱动内容生成** — 集成 DeepSeek API，自动分析项目并生成业务理解、功能描述、操作手册等文档
- **8 步引导式工作流** — 从环境检查到正式资料生成，每一步都有清晰的交互界面
- **智能代码抽取** — 自动扫描源码，按优先级分类（入口 > 路由 > 页面 > API > 组件），支持手动选码或 AI 智能选取
- **操作手册自动生成** — AI 根据业务模块生成结构化操作手册，内置自检修正机制（检测 AI 套话、技术术语准确性、格式问题）
- **多格式输出** — 一键生成 Word（.docx）和 TXT 格式的申请表、代码材料、操作手册
- **三重 DOCX 生成降级** — python-docx → 原始 OpenXML → pandoc，确保在任何环境都能生成合规文档
- **用户确认 + 手动编辑** — 所有 AI 生成内容均可人工审核修改，不做"黑盒"输出

## 📁 输出资料清单

```
软件著作权申请资料/
└── <项目名>_YYYYMMDD/
    ├── 草稿/
    │   ├── 业务理解.json / .md
    │   ├── 代码文件选择.json
    │   ├── 代码-前30页.md / 代码-后30页.md
    │   ├── 申请表信息.md
    │   └── 操作手册.md
    └── 正式资料/
        ├── 申请表信息.txt
        ├── <软件名>-代码(前30页).docx
        ├── <软件名>-代码(后30页).docx
        ├── <软件名>_操作手册.docx
        └── 生成报告.md
```

## 🚀 快速开始

### 环境要求

- Python 3.10+
- DeepSeek API Key（[注册获取](https://platform.deepseek.com)）
- （可选）[.NET 8 SDK](https://dotnet.microsoft.com/download/dotnet/8.0) — 用于完整 DOCX 校验

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/PassionHitman/ruanzhuruanjian.py 
cd ruanzhu

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动应用
python main.py
```

### 配置

1. 启动后，点击菜单栏 **设置 → API 配置**
2. 粘贴你的 DeepSeek API Key
3. 点击 **测试连接** 确认可用
4. （可选）自定义输出目录和模型名称

配置会保存到 `~/.soft-copyright/config.json`。也支持通过环境变量 `DEEPSEEK_API_KEY` 传递密钥。

## 📋 工作流程

| 步骤 | 名称 | 说明 |
|------|------|------|
| 1 | 环境检查 | 检测 Python、python-docx、OpenAI SDK、API 连接 |
| 2 | 项目选择 | 扫描项目结构，自动识别框架与版本 |
| 3 | 业务理解 | AI 分析项目，生成产品定位、功能模块等信息 |
| 4 | 代码选择 | 按优先级列出源码文件，选取 ≥ 60 页代码 |
| 5 | 申请表 | 填写软著登记申请表各项字段 |
| 6 | 截图管理 | 可选：提供界面截图或保留占位符 |
| 7 | 操作手册预览 | AI 生成手册草稿，支持预览与手动修改 |
| 8 | 正式生成 | 一键输出所有 Word 和 TXT 材料 |

## 🏗 项目架构

```
├── main.py                  # 应用入口
├── requirements.txt          # Python 依赖
├── 使用指南.md               # 详细使用手册
├── 设计文档.md               # 架构设计说明
│
├── core/                     # 核心层
│   ├── config.py             # 配置管理
│   ├── deepseek_client.py    # DeepSeek API 封装
│   ├── prompts.py            # AI 提示模板
│   ├── runner.py             # 脚本运行器
│   └── state_machine.py      # 工作流状态机
│
├── scripts/                  # 脚本层（可独立 CLI 调用）
│   ├── analyze_project.py    # 项目结构分析
│   ├── build_docx_from_md.py # Word 文档生成
│   ├── extract_code_material.py      # 代码材料抽取
│   ├── generate_application_info.py  # 申请表信息生成
│   ├── generate_business_context.py  # 业务理解
│   ├── generate_manual_draft.py      # 操作手册生成
│   └── ...
│
├── ui/                       # PyQt6 界面层
│   ├── main_window.py        # 主窗口框架
│   ├── step_env.py           # 环境检查界面
│   ├── step_project.py       # 项目选择界面
│   ├── step_business.py      # 业务理解界面
│   ├── step_code_select.py   # 代码选择界面
│   ├── step_app_form.py      # 申请表界面
│   ├── step_screenshot.py    # 截图管理界面
│   ├── step_manual_preview.py # 操作手册预览界面
│   └── step_generate.py      # 资料生成界面
│
├── assets/                   # 规则与知识文档
│   ├── application_fields.md
│   ├── code_selection_rules.md
│   ├── copyright_material_rules.md
│   └── manual_structure.md
│
└── vendor/docx-toolkit/      # .NET DOCX 工具包（可选）
```

## 🔧 技术栈

| 技术 | 用途 |
|------|------|
| Python 3.10+ | 主语言 |
| PyQt6 | 桌面 GUI |
| python-docx | DOCX 生成（主路径） |
| OpenAI SDK | DeepSeek API 客户端（兼容接口） |
| DeepSeek API | AI 内容生成引擎 |
| .NET 8 (C#) | 可选 DOCX 校验工具包 |

## 📝 特别说明

- **成本低廉** — DeepSeek API 定价约为同类产品的 1/10 ~ 1/30，生成一整套材料仅需几分钱
- **AI 输出可控** — 每个 AI 生成阶段都需要用户确认，所有判断可溯源至项目原始证据，避免编造
- **兼容性** — 无需 Claude Code 或终端交互，纯图形界面操作

## 🙏 致谢

本项目由 [SoftwareCopyright-Skill](https://github.com/Fokkyp/SoftwareCopyright-Skill)（Claude Code Skill）改造而来，将 Claude API 替换为 DeepSeek API，并包装为独立 PyQt6 桌面应用。

## 📄 许可证

本项目仅供学习和合法著作权申请使用。
