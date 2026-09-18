# GitHub 开源智能客服项目调研

调研目标：为当前 `haoka-driven-agent` 重构寻找可直接改造的开源客服智能体、RAG 客服或 Helpdesk 基础。

## 结论

按 2026-09-07 的最近提交、发布记录、源码公开程度、许可证和实际功能重新筛选后，真正值得进入下一轮源码审查的项目是 AgentDesk、Servo、Basjoo 和 Chatwoot；FastGPT、MaxKB、RAGFlow 更适合作为 RAG/Agent 基础设施参考，而不是客服产品底座。

没有找到一个同时满足“持续维护、公开源码、完整智能客服业务闭环、Python/FastAPI 技术栈、可直接拿来改造”的成熟项目。对当前仓库最稳妥的路线仍然是保留 Python/FastAPI，在本项目内补齐客服领域模型；Basjoo 用来对照技术栈，AgentDesk/Servo 用来对照客服产品能力，Chatwoot 用来对照工单、坐席和渠道运营能力。

## 2026-09-07 维护状态复核

“目前在维护”按严格标准理解为：仓库未归档，且能看到 2026 年近期提交或版本发布；只有 README 自称“production-ready”不算维护证据。

| 项目 | 维护证据 | 实际定位 | 与当前项目的结论 |
|---|---|---|---|
| [Chatwoot](https://github.com/chatwoot/chatwoot) | 2026-09-04 仍有多条提交，2026-06-10 发布 v4.14.2；36k+ stars | 成熟的全渠道客服/Helpdesk | 产品运营能力最强，但 Ruby/Rails，适合参考或作为外部客服系统集成 |
| [AgentDesk](https://github.com/huabeitech/agent-desk) | 2026-08-26 至 08-29 持续提交，v1.6.3 于 2026-07-30 发布 | AI 客服、知识库、人工接管、工单和工作台 | 最贴近“客服智能体产品”，但 Go + Next.js，适合产品形态和领域模型参考 |
| [Servo](https://github.com/ricauts/Servo) | 2026-09-01 仍有提交；402 commits | AI Service Desk：邮件转工单、AI 分流/草拟、人工审批、QA 和审计 | 功能闭环很有价值，但项目较新、社区小，适合重点拆解后择取能力 |
| [Basjoo](https://github.com/haoyiyin/basjoo) | 约 360 commits，含 CHANGELOG、测试和 E2E 报告；fork 前仍应核对最新 commit | FastAPI + Next.js 的 Agent/RAG 平台 | 与当前技术栈最接近，是迁移成本最低的候选，但仍需源码级验证 |
| [FastGPT](https://github.com/labring/FastGPT) | 2026-09-05/06 仍有提交；29k+ stars | 知识库、RAG、工作流和 Agent 平台 | 适合做知识/Agent 平台，不是完整客服工单系统；许可证有额外商业/多租户条件 |
| [MaxKB](https://github.com/1Panel-dev/MaxKB) | 2026-09-02 至 09-04 仍有提交；7k+ commits | 企业级 Agent/RAG 平台 | 适合中文知识库客服问答；GPL-3.0，商业闭源改造需先评估合规 |
| [RAGFlow](https://github.com/infiniflow/ragflow) | 2026-09-04/05 仍有提交；90k+ stars | 深度文档解析、RAG、Agent/上下文引擎 | 检索底座很强，但不是客服产品；适合替换或借鉴知识库层 |
| [FusterAI](https://github.com/aiandautomations/fusterai) | 最近可见提交为 2026-05-24，最新 release 为 2026-05-10 | Laravel/React AI Helpdesk，含 RAG、实时聊天和自动化 | 代码形态很接近完整客服，但按当前日期已不满足“近期活跃”硬标准，列入观察名单 |
| [TGO](https://github.com/tgoai/tgo) | 最近可见提交为 2026-04-28 | 多渠道 Agent 客服平台 | 功能方向匹配，但维护间隔偏长，暂不作为重构底座；另有安全披露治理风险需核查 |

### 排除项

- [langgraph-customer-support-agent](https://github.com/aperritano/langgraph-customer-support-agent)：有 LangGraph、工具、向量检索和测试样例，但主要是 mock/demo，不是完整客服底座。
- [Chatbit](https://github.com/germainelry/chatbit)：公开仓库只有极少提交，README 明确说明实际源码维护在私有仓库，不能作为可直接改造项目。
- [customer-support-ai-copilot](https://github.com/Nihal108-bi/customer-support-ai-copilot)：只有极少提交，适合作为学习示例，不满足持续维护要求。
- [agentic-rag-customer-support](https://github.com/ahmet-ozel/agentic-rag-customer-support)：功能描述较完整，但提交历史和近期维护证据不足，暂不列入优先候选。

## 补充候选（偏学习和局部能力）

| 项目 | 定位 | 与当前项目匹配度 | 建议 |
|---|---|---:|---|
| [AgentDesk](https://github.com/huabeitech/agent-desk) | 完整 AI Helpdesk：知识库、AI Agent、人工接管、工单、坐席工作台 | 高（产品层） | 最值得作为产品形态参考；若接受 Go + Next.js，可考虑 fork 改造 |
| [Basjoo](https://github.com/haoyiyin/basjoo) | FastAPI + Next.js 的 AI 客服平台，含 Agent 配置、聊天、索引、认证和调度 | 很高（技术栈） | 最接近当前 Python/FastAPI 背景，适合重点评估迁移成本 |
| [langgraph-customer-support-agent](https://github.com/aperritano/langgraph-customer-support-agent) | LangGraph 客服 Agent 教学/演示项目，含工具调用、mock 订单、向量检索和测试样例 | 中（学习） | 只适合参考图编排；不应视为完整客服底座 |
| [ChatBotAI](https://github.com/ahmetgkdemr/ChatBotAI) | FastAPI + Angular + PostgreSQL/pgvector + Ollama 的本地 RAG 客服 | 中高（RAG） | 适合参考本地部署、来源展示、向量检索；完整 Agent 能力相对弱 |
| [multi-agent-rag-customer-support](https://github.com/ro-anderson/multi-agent-rag-customer-support) | Python、LangChain、LangGraph 的多 Agent RAG 客服示例 | 中（学习） | 适合研究路由、Corrective RAG、Self-RAG；不建议直接作为生产底座 |
| [AI Customer Support Agent](https://github.com/jawwad-ali/ai-customer-support-agent) | OpenAI Agents SDK + FastAPI + PostgreSQL/pgvector + Redis + Next.js，多渠道客服 | 中（产品参考） | 适合参考多渠道、人工转接和生产化组件，但会引入较大技术栈变化 |

## 重点判断

### 1. AgentDesk：最完整的客服产品方向

项目自定位为 AI customer support system，包含知识库问答、人工转接、工单流转、坐席工作台、客户会话和嵌入式客服入口，并强调 Answerability Gate，用于判断检索结果是否足以支撑回答。[GitHub README](https://github.com/huabeitech/agent-desk)

它更像可以运行的客服产品，而不是一段 RAG Demo。代价是后端使用 Go、前端使用 Next.js，并使用 MySQL 和 Qdrant，直接迁移当前 Python 代码的成本较高。

### 2. Basjoo：当前项目最值得对照的技术路线

Basjoo 使用 FastAPI 后端，覆盖 Agent 配置、聊天、知识库索引、认证和调度，同时使用 Qdrant、PostgreSQL、Redis 和 Next.js，并支持多个 OpenAI-compatible 模型服务。[GitHub README](https://github.com/haoyiyin/basjoo)

它和当前项目在 FastAPI、外部 LLM、RAG、聊天接口这些方面更接近。适合借鉴模块拆分和生产化基础设施，但不建议不加筛选地整仓替换，因为数据库、前端、认证和异步任务都会带来较大迁移范围。

### 3. LangGraph 客服 Agent：只能作为图编排示例

该项目的 `main` 分支确实包含 `StateGraph`、`ToolNode`、工具函数、`SupportState`、向量检索实现、`tests/` 目录和 `langgraph.json`。其图是一个很小的 ReAct 循环：`agent -> tools -> agent`，工具数据主要来自内存中的 mock 数据。[agent.py](https://github.com/aperritano/langgraph-customer-support-agent/blob/main/src/support_agent/agent.py)、[tools.py](https://github.com/aperritano/langgraph-customer-support-agent/blob/main/src/support_agent/tools.py)

但它不是完整客服系统：订单、库存和退货都是 mock；人工升级只是根据消息计算 ticket 编号、打印一条日志并返回模拟的“已分配/15 分钟响应”文本，并没有客服坐席、工单持久化或真实通知通道。[tools.py](https://github.com/aperritano/langgraph-customer-support-agent/blob/main/src/support_agent/tools.py)

它的会话状态只有一个 `messages` 字段；`agent.py` 默认使用 `workflow.compile()`，没有在应用代码中配置持久化 checkpointer。所谓 REST API 主要是通过 `langgraph dev` 提供的开发服务，而不是仓库自建的 FastAPI 业务 API。README 自己的 “Next Steps” 也把接入真实订单系统、增加认证、创建 React UI 等列为后续工作。[README](https://github.com/aperritano/langgraph-customer-support-agent/blob/main/README.md)

另外，README 的“50+ unit tests”应谨慎理解为仓库作者的声明；仓库确实存在测试文件，但在没有实际安装依赖并运行测试的情况下，不能把 README 中的数量或通过状态当作已验证事实。

当前项目已经有客服 Agent、多个工具、会话历史和 Chroma 检索器，因此可以把它作为架构参考：将隐式的 LLM 工具选择逐步改成显式的状态节点和条件边，增加 answerability、人工升级和评估节点。

### 4. ChatBotAI：最适合补强本地 RAG

ChatBotAI 采用 FastAPI、Angular、PostgreSQL/pgvector、Ollama 和 sentence-transformers，支持本地部署、语义检索、来源展示和流式聊天。[GitHub README](https://github.com/ahmetgkdemr/ChatBotAI)

它更偏 RAG 客服聊天应用，不是完整业务 Agent。适合参考向量库、来源引用和本地模型部署，不适合作为当前客服工具编排层的唯一重构目标。

## 针对当前项目的推荐顺序

1. 保持当前 Python/FastAPI 主线，先以 Basjoo 为参照，拆出会话、知识库、Agent、用户身份和异步索引等边界。
2. 以 AgentDesk 和 Servo 为产品能力参照，优先补齐人工接管、工单、审批、审计、知识命中依据和客服工作台。
3. 以 Chatwoot 为运营能力参照，评估渠道接入、坐席分配、会话状态、SLA 和报表是否需要自建或外接。
4. 如果知识库规模和文档解析成为瓶颈，再单独评估接入 RAGFlow、FastGPT 或 MaxKB，不要因此把整个项目改造成纯 RAG 平台。
5. 把 `langgraph-customer-support-agent` 降级为图编排学习材料，不作为重构底座。

## 不建议的做法

- 不建议把项目直接改名为“RAG 系统”，因为订单、转人工、密码重置和会话管理都属于客服业务能力。
- 不建议一开始就改成多 Agent。当前单 Agent + 工具已经能表达业务，先把路由、状态、检索质量和人工升级做好。
- 不建议直接复制某个仓库的全部代码。优先提取领域模型、状态机、工具边界、知识库生命周期和评估方法。

## 许可证与安全提示

Chatwoot 核心代码标注 MIT，Servo 和 FusterAI 标注 Apache-2.0/MIT，RAGFlow 标注 Apache-2.0；MaxKB 为 GPL-3.0。FastGPT 和 TGO 的 Apache 衍生许可证对多租户、品牌标识或商业使用存在额外条件。实际 fork 前仍需逐项检查 LICENSE、依赖许可证、安全公告、部署配置和最新提交，不能只依据 README 判断。
