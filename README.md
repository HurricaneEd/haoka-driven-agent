这是一个智能客服项目。系统使用 FastAPI 提供服务，通过 LangChain Agent 检索知识库，并使用 SQLite 与 Chroma 构建支持父子块检索的 Markdown 知识库。

> [!IMPORTANT]
> 本仓库中的业务内容均为**示例数据**，仅用于展示和测试程序功能。

## 功能概览

- 邮箱注册、登录、退出和服务端会话管理
- 登录后使用智能客服及知识库管理功能
- 个人信息页面支持登录用户修改密码
- 仅接收 `.md` 知识文档，支持上传、处理状态、切分预览、重试和删除
- Markdown 标题感知切分与父子块检索
- 向量 MMR 与中文 BM25 混合召回，再通过 RRF 融合排序
- SQLite 保存用户、会话、文档台账和完整父文档
- Chroma 保存用于检索的子块向量
- Docker Compose 部署

## RAG 实现思路

项目采用“一份 Markdown 对应一个商品或主题”的约定：

```text
Markdown 文档
    ├── 完整父文档 → SQLite
    └── 标题感知子块 → Embedding → Chroma

用户问题
    → 向量 MMR + 中文 BM25
    → RRF 融合排序
    → 根据商品名称和自动别名聚合
    → 展开对应完整父文档
    → 客服 Agent 组织回答
```

子块只负责定位商品和相关章节，最终交给模型的是对应商品的完整父文档。

## 技术栈

- Python 3.11
- FastAPI
- LangChain Agent
- DeepSeek 或其他 OpenAI 兼容聊天模型
- SiliconFlow 或其他 OpenAI 兼容 Embedding 服务
- Chroma
- SQLite / SQLAlchemy
- 原生 HTML、CSS 和 JavaScript 前端

## 快速开始

### 1. 配置环境变量

复制示例配置：

```bash
cp .env.example .env
```

至少需要填写聊天模型和向量模型所需的 API Key：

```dotenv
DEEPSEEK_API_KEY=your-chat-api-key
SILICONFLOW_API_KEY=your-embedding-api-key
```

### 2. 使用 Docker 启动

```bash
docker compose up -d --build
```

用户登录后直接上传 `product/` 中的示例 Markdown 即可建立索引。

然后访问：

- Web 页面：<http://localhost:8000>
- API 文档：<http://localhost:8000/api/docs>
- 健康检查：<http://localhost:8000/health>

### 3. 本地启动

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
pip install -r requirements.txt
python main.py
```

## 主要配置

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `MODEL_NAME` | `deepseek-v4-flash` | 聊天模型名称 |
| `EMBEDDING_MODEL` | `BAAI/bge-large-zh-v1.5` | Embedding 模型名称 |
| `RAG_CHILD_CHUNK_SIZE` | `400` | 子块最大字符数 |
| `RAG_CHILD_CHUNK_OVERLAP` | `60` | 相邻子块重叠字符数 |
| `RAG_FETCH_K` | `30` | 检索候选数量 |
| `RAG_MMR_LAMBDA` | `0.7` | MMR 相关性与多样性权衡 |
| `RAG_HYBRID_ENABLED` | `true` | 是否启用混合检索 |
| `RAG_LEXICAL_WEIGHT` | `0.35` | 词法检索在 RRF 中的权重 |
| `KNOWLEDGE_UPLOAD_MAX_MB` | `20` | 单个上传文件大小限制 |

完整配置请查看 [`.env.example`](.env.example)。

## 项目结构

```text
app/
├── api.py                    # 登录、对话和知识库 API
├── chatbot.py                # 客服 Agent 与工具编排
├── database.py               # SQLite 数据模型和数据访问
├── knowledge_documents.py    # 文档上传、处理、重试和删除
└── rag/
    ├── parsers.py            # Markdown 解析
    ├── identity.py           # 文档身份和商品别名
    ├── chunkers.py           # 标题感知子块切分
    ├── ingestion.py          # 文档摄入编排
    ├── parents.py            # SQLite 父文档存储
    ├── retrieval.py          # 混合检索、商品聚合和父块展开
    └── stores.py             # Chroma 适配层
product/                      # 示例商品 Markdown
index.html                    # Web 页面
```

## 部分截图

![image-20260920142003032](C:\Users\86183\AppData\Roaming\Typora\typora-user-images\image-20260920142003032.png)

![image-20260920141852892](C:\Users\86183\AppData\Roaming\Typora\typora-user-images\image-20260920141852892.png)