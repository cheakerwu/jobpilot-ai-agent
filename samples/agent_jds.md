# Agent 开发岗位测试 JD

这些 JD 可用于 JobPilot 的手动导入、CSV 导入、岗位分析、证据匹配和定制简历生成测试。CSV 版本见 `samples/agent_jds.csv`。

## 1. AI Agent应用开发工程师

公司：星河智能科技
城市：上海
薪资：25-40K

岗位描述：

负责面向企业知识库和内部运营场景的 AI Agent 应用开发，设计从用户意图理解、工具调用、任务规划到结果校验的完整链路。需要与产品、后端和算法团队协作，将大模型能力落地到可用的 Web 产品中。核心工作包括 Agent 工作流编排、工具接入、结构化输出、失败重试、日志追踪和效果评估。

任职要求：

1. 熟悉 Python 和 FastAPI，具备后端服务开发经验。
2. 了解 LangChain、LangGraph、LlamaIndex 或类似 Agent 框架。
3. 熟悉 RAG、function calling、tool use、prompt engineering。
4. 有数据库经验，熟悉 PostgreSQL、Redis 或 SQLite。
5. 能设计可观测、可评测、可回滚的 Agent 流程。
6. 加分项：有 Docker、Celery、OpenTelemetry、LangSmith 经验。

## 2. Agentic RAG工程师

公司：启明数据智能
城市：北京
薪资：30-50K

岗位描述：

负责构建面向金融和咨询行业的 Agentic RAG 系统，支持多文档检索、引用溯源、多轮追问、任务拆解和报告生成。需要设计检索增强、证据约束、答案校验和人工审核机制，提升大模型回答的准确性和可解释性。

任职要求：

1. 熟悉向量检索、embedding、rerank、chunking 策略。
2. 熟悉 LlamaIndex、LangChain 或 Haystack。
3. 熟悉 Python 服务开发和 API 设计。
4. 能处理 PDF、Word、网页等非结构化文档。
5. 理解幻觉控制、引用来源、评测集构建。
6. 加分项：有 Qdrant、Milvus、Elasticsearch、PostgreSQL pgvector 经验。

## 3. Browser Agent开发工程师

公司：灵动自动化
城市：深圳
薪资：28-45K

岗位描述：

负责开发基于浏览器的 AI Agent，帮助用户自动完成网页信息提取、后台录入、表单填写和跨站点操作。需要构建稳定的网页理解、动作规划、页面状态检测、异常恢复和人工接管机制，提升自动化任务成功率。

任职要求：

1. 熟悉 Playwright、Selenium 或 browser-use 等浏览器自动化技术。
2. 熟悉 Python 或 TypeScript。
3. 了解 DOM 解析、截图理解、网页状态管理。
4. 熟悉 LLM 工具调用和多步骤任务规划。
5. 能处理登录态、超时、弹窗、页面跳转等复杂场景。
6. 加分项：有任务回放、操作审计、沙箱隔离经验。

## 4. 多Agent工作流工程师

公司：元策AI
城市：杭州
薪资：35-55K

岗位描述：

负责设计和实现多 Agent 协作系统，用于市场调研、竞品分析、代码审查和自动报告生成。需要将复杂任务拆分为 Planner、Researcher、Executor、Reviewer 等角色，并通过状态机、消息协议和评测机制保证协作质量。

任职要求：

1. 熟悉 AutoGen、CrewAI、LangGraph 或 Microsoft Agent Framework。
2. 理解多 Agent 协作、任务分解、角色边界和冲突处理。
3. 熟悉 Python 异步编程和后端工程化。
4. 能设计 Agent 状态、事件、消息和执行记录。
5. 有 LLM 输出结构化、错误重试、人工确认机制经验。
6. 加分项：有复杂工作流产品或低代码编排经验。

## 5. Agent评测与可观测性工程师

公司：观测云智能
城市：上海
薪资：30-48K

岗位描述：

负责建设 AI Agent 系统的评测和可观测性平台，覆盖任务成功率、工具调用准确率、响应质量、成本、延迟、失败类型和人工干预率等指标。需要构建离线评测集、在线监控、回放系统和质量分析看板。

任职要求：

1. 熟悉 LLM 应用评测方法，包括 golden dataset、LLM-as-judge、规则评测和人工标注。
2. 熟悉 Python、FastAPI、SQLAlchemy。
3. 熟悉日志、trace、metrics、OpenTelemetry 等可观测性体系。
4. 能分析 Agent 失败原因并提出流程改进方案。
5. 熟悉 pytest 或其他自动化测试框架。
6. 加分项：有 LangSmith、Arize Phoenix、Promptfoo 或 Ragas 经验。

## 6. AI Agent平台后端工程师

公司：云栈科技
城市：成都
薪资：22-38K

岗位描述：

负责建设企业级 AI Agent 平台后端，支持 Agent 配置、工具市场、权限管理、任务队列、执行记录、模型路由和多租户数据隔离。需要将 Agent 能力平台化，支持多个业务团队快速创建和发布自己的 Agent 应用。

任职要求：

1. 熟悉 Python 后端开发，掌握 FastAPI、SQLAlchemy 和 RESTful API 设计。
2. 熟悉 PostgreSQL、Redis、消息队列和后台任务。
3. 理解模型供应商接入、模型路由、API Key 安全管理。
4. 了解 Agent 工具调用、工作流编排和执行沙箱。
5. 具备良好的工程化意识，能编写测试和文档。
6. 加分项：有 SaaS、多租户、权限系统、Docker 部署经验。
