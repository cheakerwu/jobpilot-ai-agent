# JobPilot

JobPilot 是一个个人求职 CRM + Agent Copilot。它不再依赖招聘网站爬虫作为主流程，而是通过手动粘贴、CSV/Excel 导入等稳定数据源建立岗位池，再结合个人经历证据库完成岗位分析、推荐排序、定制简历生成和 Agent 执行记录追踪。

## 核心价值

直接把简历和 JD 发给大模型，只能得到一次性的文本建议。JobPilot 把求职流程产品化：

- 批量管理岗位池，而不是一次分析一个岗位。
- 用个人经历证据库约束分析和简历生成，减少编造风险。
- 保存匹配分、风险分、推荐等级、简历可补强项和建议动作。
- 记录 Agent 每一步执行过程，便于复盘和调试。
- 为每个岗位保存定制简历版本，后续可继续扩展投递反馈闭环。

## 当前能力

- 岗位导入：手动粘贴 JD、CSV/Excel 批量导入、PDF JD 自动识别、浏览器插件采集。
- 岗位管理：分页列表、详情、状态更新、删除。
- 证据库：维护技能、项目、工作经历、教育经历等事实证据，支持 PDF 简历自动抽取。
- 岗位分析：规则分析为基础，配置 API Key 后可启用 LLM 增强分析。
- 模型设置：Web 页面自由选择 provider、模型名、token 上限和调用限额。
- Agent 工作流：记录 `parse_jd`、`load_evidence`、`score_match`、`persist_result` 等步骤。
- 简历版本：基于岗位分析和证据库生成定制简历版本。
- Web API：FastAPI 提供产品化接口。
- 测试：覆盖数据源、规则分析器和数据库基础行为。

## 技术栈

- Python 3.12+
- FastAPI
- SQLAlchemy
- SQLite
- Pydantic
- Pandas / OpenPyXL
- pypdf
- Anthropic / OpenAI-compatible LLM providers
- Pytest

## 快速开始

安装依赖：

```bash
pip install -r requirements.txt
```

配置环境变量：

```bash
copy .env.example .env
```

根据使用的模型提供商配置其中一个 API Key：

```text
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
DEEPSEEK_API_KEY=
DASHSCOPE_API_KEY=
```

准备本地配置：

```bash
copy config\config.example.yaml config\config.yaml
copy config\user_profile.example.json config\user_profile.json
```

然后按自己的情况修改 `config/user_profile.json`。该文件通常包含姓名、联系方式、学校和项目经历，默认不会提交到 Git。

启动 Web 服务：

```bash
python run_web.py
```

默认访问：

```text
http://localhost:8000
```

运行测试：

```bash
python -m pytest -q
```

## 主要接口

岗位导入：

```text
POST /api/imports/manual
POST /api/imports/csv
POST /api/imports/pdf-jd
POST /api/imports/capture
GET  /api/imports/{batch_id}
```

岗位池：

```text
GET    /api/jobs
GET    /api/jobs/{job_id}
PATCH  /api/jobs/{job_id}
DELETE /api/jobs/{job_id}
```

证据库：

```text
GET    /api/evidence
POST   /api/evidence
POST   /api/evidence/import-resume-pdf
PATCH  /api/evidence/{evidence_id}
DELETE /api/evidence/{evidence_id}
POST   /api/evidence/init
```

岗位分析：

```text
POST /api/analyses/jobs/{job_id}
POST /api/analyses/batch
GET  /api/analyses/{analysis_id}
GET  /api/analyses/jobs/{job_id}/latest
```

简历版本：

```text
POST /api/resumes/generate
GET  /api/resumes
GET  /api/resumes/{version_id}
GET  /api/resumes/jobs/{job_id}
```

Agent 记录：

```text
GET /api/agent-runs
GET /api/agent-runs/{run_id}
GET /api/agent-runs/{run_id}/steps
```

模型设置：

```text
GET   /api/settings/models
PATCH /api/settings/models
```

## 项目结构

```text
job_agent/
├── config/
│   ├── config.yaml
│   └── user_profile.json
├── src/
│   ├── agent/          # Agent 状态机与执行状态
│   ├── analyzer/       # 规则/LLM/混合岗位分析器
│   ├── resume/         # 基于证据库的简历生成
│   ├── sources/        # 可插拔岗位数据源
│   ├── storage/        # SQLAlchemy 模型与数据库访问
│   └── utils/
├── tests/
├── web_api/
│   ├── routers/
│   ├── static/
│   └── templates/
├── browser_extension/  # 本地浏览器岗位采集插件
├── requirements.txt
└── run_web.py
```

## 设计原则

- 不把绕过招聘平台反爬作为项目主线。
- 不自动批量投递，关键动作应由用户确认。
- 不编造经历；证据暂未充分体现时输出简历可补强项和风险提示。
- LLM 输出尽量结构化，便于保存、复盘和评测。
- 数据源、分析器、简历生成器都应保持可插拔。

## Git 与隐私

首次上传 GitHub 前，请确认以下文件只保留在本地：

```text
.env
config/config.yaml
config/user_profile.json
data/
logs/
```

仓库中只提交 `.env.example`、`config/config.example.yaml` 和 `config/user_profile.example.json`。如果曾经误提交 API Key 或真实简历信息，应立即重置对应 Key，并清理 Git 历史后再公开仓库。

## 后续可扩展方向

- 多用户登录和数据隔离。
- 浏览器插件一键保存岗位。
- Redis + 任务队列处理批量分析。
- PostgreSQL 替代 SQLite。
- 简历 PDF / DOCX 导出。
- 投递看板和反馈学习。
- 公开招聘 API / ATS 数据源接入。
