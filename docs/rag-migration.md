# RAG 知识库改造说明

## 本阶段结果

知识库已从“Markdown 固定标题切分 + 业务层直连 Chroma + 全量清空重建”改为独立管线：

```text
Markdown -> 自动身份/别名 -> 完整父文档（SQLite）+ 标题感知子块（Chroma）
查询 -> 向量 MMR + 中文 BM25 -> RRF 融合 -> 按商品聚合 -> 展开父文档 -> 客服 Agent
```

- 仅支持 `.md` Markdown 文档；上传其他格式会被拒绝，目录摄入会忽略非 `.md` 文件。
- Markdown 不再读取 frontmatter：文件名生成内部 `doc_id`，首个一级标题生成展示名称。
- 商品别名由标题自动生成；例如四川联通卡会获得“四川卡”等高精度别名。
- 每份 Markdown 的完整正文作为父文档保存；先按结构分节，超长章节再按 `RAG_CHILD_CHUNK_SIZE` 和 `RAG_CHILD_CHUNK_OVERLAP` 切成检索子块。
- 子块命中后按 `doc_id` 聚合并展开完整父文档，避免不同商品的相似章节互串。
- 泛称涉及多款商品时要求用户确认；只有明确的对比问题才会展开多个父文档。
- 块 ID 基于内容哈希，不再依赖章节位置。
- 普通摄入按文档哈希跳过未变化内容；变化时只替换对应 `doc_id`。
- Chroma 被适配器封装，客服 Agent 不再直接访问底层 vectorstore。
- SQLite 继续作为块级镜像，保留现有 API 和页面的数据契约。
- 登录后可在知识库页面上传文件、查看处理状态、预览切分结果、重试失败任务或删除文档。
- `knowledge_documents` 保存文档级台账；状态依次为 `pending`、`processing`、`ready` 或 `error`。
- 上传接口立即返回 `202`，解析、切分和向量化由 FastAPI 后台任务继续执行。
- 检索同时考虑语义相似度和中文/数字精确命中。

## 知识库接口

所有接口都需要登录令牌：

```text
POST   /knowledge/documents                    上传文件
GET    /knowledge/documents                    文档台账
GET    /knowledge/documents/{doc_id}/chunks    切分预览
POST   /knowledge/documents/{doc_id}/retry     重试处理
DELETE /knowledge/documents/{doc_id}           删除文档、知识块和向量
```

上传目录和大小限制由 `KNOWLEDGE_UPLOAD_PATH`、`KNOWLEDGE_UPLOAD_MAX_MB` 配置。混合检索可通过 `RAG_HYBRID_ENABLED` 开关，词法权重由 `RAG_LEXICAL_WEIGHT` 调整。

## 使用

增量摄入 `product/` 目录：

```bash
python scripts/ingest_products.py
```

只验证解析、切分并更新 SQLite，不调用 Embedding API：

```bash
python scripts/ingest_products.py --sqlite-only
```

强制重新生成全部现有文档的向量：

```bash
python scripts/ingest_products.py --force
```

按文档删除：

```bash
python scripts/ingest_products.py --delete-doc DOC_ID
```

## 设计来源和边界

本次设计参考了 [Basjoo](https://github.com/haoyiyin/basjoo) 公开文档中的文件摄入、文档生命周期和存储隔离思路。其当前主分支已转向 R2R，旧版自建 KB 源文件未能完整取得，因此本仓库没有逐行复制 Basjoo 代码；实现是针对本项目现有 FastAPI、SQLite、Chroma 和 SiliconFlow 接口重新编写的。

当前 BM25 会读取现有 Chroma 文档，适合当前的小型知识库。数据规模扩大后应将词法索引迁移到 Elasticsearch/OpenSearch，或换成原生支持稀疏向量的存储。

后台任务目前运行在 Web 进程内；服务在处理期间重启会留下 `pending` 或 `processing` 状态，可从页面手动重试。生产环境下一阶段应接入持久任务队列，重排模型（reranker）尚未引入。
