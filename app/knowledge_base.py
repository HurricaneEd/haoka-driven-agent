# -*- coding: utf-8 -*-
"""知识库门面。

对外只暴露摄入和检索能力；Chroma、Embedding、切分器都封装在 app.rag 内。
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from langchain_core.documents import Document

from app.rag.chunkers import ChunkingConfig, StructureAwareChunker
from app.rag.embeddings import SiliconFlowEmbeddings
from app.rag.ingestion import IngestionService, PreparedDocument
from app.rag.retrieval import RetrievalService
from app.rag.schemas import IngestionResult, RagChunk
from app.rag.stores import ChromaVectorStore
from config import settings


class KnowledgeBaseManager:
    """组合 RAG 管线，并为 API、Agent 和脚本提供稳定入口。"""

    def __init__(self) -> None:
        api_key = settings.embedding_api_key or settings.siliconflow_api_key
        embeddings = SiliconFlowEmbeddings(
            api_key=api_key,
            model=settings.embedding_model,
            base_url=settings.embedding_api_base,
        )
        self.store = ChromaVectorStore(embeddings, settings.chroma_db_path)
        chunker = StructureAwareChunker(ChunkingConfig(
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
        ))
        self.ingestion = IngestionService(store=self.store, chunker=chunker)
        self.retrieval = RetrievalService(
            self.store,
            fetch_k=settings.rag_fetch_k,
            lambda_mult=settings.rag_mmr_lambda,
            hybrid_enabled=settings.rag_hybrid_enabled,
            lexical_weight=settings.rag_lexical_weight,
            rrf_k=settings.rag_rrf_k,
        )
        self._ensure_seeded()

    def _ensure_seeded(self) -> None:
        if not settings.seed_demo_data or self.count() > 0:
            return
        prepared = self.ingestion.prepare_text(
            doc_id="seed-demo",
            title="演示知识",
            content=(
                "## 激活流程\n下单后按随卡说明完成实名认证，再激活使用。\n\n"
                "## 注销政策\n可在运营商 APP 内自助销户或联系客服。"
            ),
            category="demo",
            tags=("激活", "注销"),
            source="seed",
        )
        self.ingestion.ingest(prepared)

    def prepare_file(self, path: Path, metadata: Dict[str, Any] | None = None) -> PreparedDocument:
        return self.ingestion.prepare_file(path, metadata)

    def prepare_text(self, **kwargs: Any) -> PreparedDocument:
        return self.ingestion.prepare_text(**kwargs)

    def ingest(self, prepared: PreparedDocument, force: bool = False) -> IngestionResult:
        return self.ingestion.ingest(prepared, force=force)

    def add_chunks(self, chunks: Sequence[RagChunk]) -> None:
        """兼容旧调用；新摄入代码应优先使用 ingest。"""
        self.store.upsert_chunks(chunks)

    def delete_document(self, doc_id: str) -> int:
        return self.ingestion.delete(doc_id)

    def clear_all(self) -> int:
        """仅供显式重建使用，普通入库不再调用。"""
        return self.store.clear_all()

    def retrieve(
        self, query: str, k: int = 6, category: Optional[str] = None
    ) -> List[Document]:
        return self.retrieval.retrieve(query, k=k, category=category)

    def search(
        self, query: str, k: int = 5, category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return self.retrieval.search(query, k=k, category=category)

    def get_all_documents(self) -> List[Document]:
        return self.store.get_all_documents()

    def count(self) -> int:
        return self.store.count()


_kb_manager: Optional[KnowledgeBaseManager] = None


def get_knowledge_base() -> KnowledgeBaseManager:
    global _kb_manager
    if _kb_manager is None:
        _kb_manager = KnowledgeBaseManager()
    return _kb_manager


def initialize_knowledge_base() -> KnowledgeBaseManager:
    return get_knowledge_base()
