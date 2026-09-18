"""向量存储适配层；业务代码不直接接触 Chroma。"""

from typing import Any, Dict, List, Optional, Sequence, Tuple

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app.rag.schemas import RagChunk


class ChromaVectorStore:
    def __init__(self, embeddings: Embeddings, persist_directory: str) -> None:
        self._store = Chroma(
            collection_name="knowledge_base",
            embedding_function=embeddings,
            persist_directory=persist_directory,
            collection_metadata={"hnsw:space": "cosine"},
        )

    def _document_data(self, doc_id: str) -> Dict[str, Any]:
        return self._store.get(where={"doc_id": doc_id}, include=["metadatas"])

    def get_document_hash(self, doc_id: str) -> str | None:
        metadatas = self._document_data(doc_id).get("metadatas") or []
        hashes = {metadata.get("document_hash") for metadata in metadatas if metadata}
        return hashes.pop() if len(hashes) == 1 else None

    def upsert_chunks(self, chunks: Sequence[RagChunk]) -> None:
        if not chunks:
            return
        self._store.add_texts(
            texts=[chunk.content for chunk in chunks],
            metadatas=[chunk.vector_metadata() for chunk in chunks],
            ids=[chunk.id for chunk in chunks],
        )

    def replace_document(self, doc_id: str, chunks: Sequence[RagChunk]) -> None:
        existing_ids = set(self._document_data(doc_id).get("ids") or [])
        self.upsert_chunks(chunks)
        # 新块全部写入成功后再删旧块，Embedding 请求失败时不会先把在线知识删空。
        current_ids = {chunk.id for chunk in chunks}
        stale_ids = list(existing_ids - current_ids)
        if stale_ids:
            self._store.delete(ids=stale_ids)

    def delete_document(self, doc_id: str) -> int:
        ids = self._document_data(doc_id).get("ids") or []
        if ids:
            self._store.delete(ids=ids)
        return len(ids)

    def mmr_search(
        self,
        query: str,
        *,
        k: int,
        fetch_k: int,
        lambda_mult: float,
        category: Optional[str] = None,
    ) -> List[Document]:
        filter_ = {"category": category} if category else None
        return self._store.max_marginal_relevance_search(
            query,
            k=k,
            fetch_k=fetch_k,
            lambda_mult=lambda_mult,
            filter=filter_,
        )

    def similarity_search(
        self, query: str, *, k: int, category: Optional[str] = None
    ) -> List[Tuple[Document, float]]:
        filter_ = {"category": category} if category else None
        return self._store.similarity_search_with_score(query, k=k, filter=filter_)

    def get_all_documents(self) -> List[Document]:
        data = self._store.get()
        metadatas = data.get("metadatas") or []
        return [
            Document(
                page_content=content,
                metadata=metadatas[index] if index < len(metadatas) else {},
            )
            for index, content in enumerate(data.get("documents") or [])
        ]

    def clear_all(self) -> int:
        data = self._store.get()
        ids = data.get("ids") or []
        if ids:
            self._store.delete(ids=ids)
        return len(ids)

    def count(self) -> int:
        return self._store._collection.count()
