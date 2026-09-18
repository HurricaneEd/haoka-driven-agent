"""文档摄入编排：解析、切分、按文档增量替换。"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Protocol, Sequence

from app.rag.chunkers import StructureAwareChunker
from app.rag.parsers import DocumentParserRegistry
from app.rag.schemas import IngestionResult, RagChunk, RagDocument


class IngestionStore(Protocol):
    def get_document_hash(self, doc_id: str) -> str | None:
        ...

    def replace_document(self, doc_id: str, chunks: Sequence[RagChunk]) -> None:
        ...

    def delete_document(self, doc_id: str) -> int:
        ...


@dataclass(frozen=True)
class PreparedDocument:
    document: RagDocument
    chunks: tuple[RagChunk, ...]


class IngestionService:
    def __init__(
        self,
        store: IngestionStore | None,
        parser_registry: DocumentParserRegistry | None = None,
        chunker: StructureAwareChunker | None = None,
    ) -> None:
        self.store = store
        self.parsers = parser_registry or DocumentParserRegistry()
        self.chunker = chunker or StructureAwareChunker()

    def prepare_file(self, path: Path, metadata: Dict[str, Any] | None = None) -> PreparedDocument:
        document = self.parsers.parse(path, metadata)
        return PreparedDocument(document=document, chunks=tuple(self.chunker.split(document)))

    def prepare_text(
        self,
        *,
        doc_id: str,
        title: str,
        content: str,
        category: str = "knowledge",
        tags: Sequence[str] = (),
        source: str = "api",
    ) -> PreparedDocument:
        document = RagDocument(
            doc_id=doc_id,
            title=title,
            content=content,
            source=source,
            category=category,
            tags=tuple(tags),
        )
        return PreparedDocument(document=document, chunks=tuple(self.chunker.split(document)))

    def ingest(self, prepared: PreparedDocument, force: bool = False) -> IngestionResult:
        if self.store is None:
            raise RuntimeError("当前 IngestionService 未配置向量存储")
        document = prepared.document
        if not force and self.store.get_document_hash(document.doc_id) == document.content_hash:
            return IngestionResult(document.doc_id, "skipped", len(prepared.chunks), document.content_hash)
        self.store.replace_document(document.doc_id, prepared.chunks)
        return IngestionResult(document.doc_id, "indexed", len(prepared.chunks), document.content_hash)

    def delete(self, doc_id: str) -> int:
        if self.store is None:
            raise RuntimeError("当前 IngestionService 未配置向量存储")
        return self.store.delete_document(doc_id)

