"""可替换的 RAG 知识库管线。"""

from app.rag.chunkers import ChunkingConfig, StructureAwareChunker
from app.rag.ingestion import IngestionService, PreparedDocument
from app.rag.parsers import DocumentParserRegistry, UnsupportedDocumentError
from app.rag.schemas import IngestionResult, RagChunk, RagDocument

__all__ = [
    "ChunkingConfig",
    "DocumentParserRegistry",
    "IngestionResult",
    "IngestionService",
    "PreparedDocument",
    "RagChunk",
    "RagDocument",
    "StructureAwareChunker",
    "UnsupportedDocumentError",
]
