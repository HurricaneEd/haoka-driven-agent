# -*- coding: utf-8 -*-
"""知识库管理器：ChromaDB 向量检索侧。

Embedding 走硅基流动（SiliconFlow）OpenAI 兼容接口：BAAI/bge-large-zh-v1.5，
无需本地模型下载（HuggingFace 网络不通也不受影响）。

- 检索大脑（Chroma）在此
- SQLite knowledge_base 镜像（台账/审计/重建）由 scripts/ingest_products.py 双写维护
- 双库键值一致：SQLite 主键 = Chroma id = f"{doc_id}_c{chunk_index}"
"""
from typing import Any, Dict, List, Optional

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from config import settings


class KnowledgeBaseManager:
    """Chroma 向量库管理器（检索侧）。"""

    def __init__(self):
        api_key = settings.embedding_api_key or settings.siliconflow_api_key
        self.embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=api_key,
            base_url=settings.embedding_api_base,
        )
        self.vectorstore = Chroma(
            collection_name="knowledge_base",
            embedding_function=self.embeddings,
            persist_directory=settings.chroma_db_path,
            collection_metadata={"hnsw:space": "cosine"},
        )
        self._ensure_seeded()

    def _ensure_seeded(self):
        """默认关闭（SEED_DEMO_DATA=False）。开启且集合为空时才种演示数据。"""
        if not settings.seed_demo_data:
            return
        if self.vectorstore._collection.count() > 0:
            return
        texts = [
            "用户激活流程：下单后按随卡说明完成实名认证，再激活使用。",
            "退卡政策：激活后如需注销，可在运营商 APP 内自助销户或联系客服。",
        ]
        metadatas = [
            {"category": "demo", "title": "激活流程", "tags": "激活,实名"},
            {"category": "demo", "title": "注销政策", "tags": "注销,销户"},
        ]
        ids = [f"seed_demo_{i}" for i in range(len(texts))]
        self.vectorstore.add_texts(texts, metadatas=metadatas, ids=ids)

    # ── 写入 ────────────────────────────────────────────────

    def add_chunks(self, chunks) -> None:
        """批量写入 Chunk 列表（与 SQLite 每行严格 1:1）。"""
        self.vectorstore.add_texts(
            texts=[c.content for c in chunks],
            metadatas=[c.metadata() for c in chunks],
            ids=[c.id for c in chunks],
        )

    def clear_all(self) -> None:
        """清空整个集合（重灌前调用，幂等）。"""
        existing = self.vectorstore.get()
        ids = existing.get("ids") or []
        if ids:
            self.vectorstore.delete(ids)

    # ── 读取 ────────────────────────────────────────────────

    def search(self, query: str, k: int = 5,
               category: Optional[str] = None) -> List[Dict[str, Any]]:
        """语义检索，返回 [{content, metadata, score}]。"""
        filter_ = {"category": category} if category else None
        docs_and_scores = self.vectorstore.similarity_search_with_score(
            query, k=k, filter=filter_
        )
        results = []
        for doc, distance in docs_and_scores:
            content = doc.page_content
            if len(content) > 500:
                content = content[:500] + "..."
            m = doc.metadata
            results.append({
                "content": content,
                "metadata": {
                    "doc_id": m.get("doc_id"),
                    "title": m.get("title"),
                    "section": m.get("section"),
                    "chunk_index": m.get("chunk_index"),
                    "category": m.get("category"),
                    "tags": [t.strip() for t in (m.get("tags") or "").split(",") if t.strip()],
                    "source": m.get("source"),
                },
                "score": round(max(0.0, min(1.0, 1.0 - distance)), 4),
            })
        return results

    def get_all_documents(self) -> List[Document]:
        """返回集合内全部 Document（含 metadata）。"""
        data = self.vectorstore.get()
        metadatas = data.get("metadatas") or []
        return [
            Document(
                page_content=content,
                metadata=metadatas[i] if i < len(metadatas) else {},
            )
            for i, content in enumerate(data.get("documents") or [])
        ]

    def count(self) -> int:
        return self.vectorstore._collection.count()


# 共享单例：API 生命周期与独立脚本共用同一个向量库连接。
_kb_manager: Optional[KnowledgeBaseManager] = None


def get_knowledge_base() -> KnowledgeBaseManager:
    """返回共享单例，首次调用时创建。"""
    global _kb_manager
    if _kb_manager is None:
        _kb_manager = KnowledgeBaseManager()
    return _kb_manager


def initialize_knowledge_base() -> KnowledgeBaseManager:
    """应用启动时调用：初始化（创建表/集合）。返回共享单例。"""
    return get_knowledge_base()
