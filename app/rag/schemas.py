"""RAG 层的领域模型，不依赖 SQLite、Chroma 或 LangChain。"""

from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Dict, Iterable, Tuple

from app.rag.identity import derive_document_aliases, normalize_aliases


def normalize_tags(tags: Iterable[str] | str | None) -> Tuple[str, ...]:
    if not tags:
        return ()
    values = tags.split(",") if isinstance(tags, str) else tags
    return tuple(dict.fromkeys(str(tag).strip() for tag in values if str(tag).strip()))


def content_digest(content: str) -> str:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    return sha256(normalized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RagDocument:
    """解析后的源文档。"""

    doc_id: str
    title: str
    content: str
    source: str
    category: str = "knowledge"
    tags: Tuple[str, ...] = ()
    aliases: Tuple[str, ...] = ()
    metadata: Dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "doc_id", self.doc_id.strip())
        object.__setattr__(self, "title", self.title.strip())
        object.__setattr__(self, "content", self.content.strip())
        object.__setattr__(self, "tags", normalize_tags(self.tags))
        aliases = normalize_aliases(self.aliases) or derive_document_aliases(self.title, self.doc_id)
        object.__setattr__(self, "aliases", aliases)
        if not self.doc_id:
            raise ValueError("doc_id 不能为空")
        if not self.content:
            raise ValueError(f"文档 {self.doc_id} 没有可入库内容")
        if not self.content_hash:
            fingerprint = json.dumps(
                {
                    "title": self.title,
                    "content": self.content,
                    "source": self.source,
                    "category": self.category,
                    "tags": self.tags,
                    "aliases": self.aliases,
                    "metadata": self.metadata,
                },
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
            object.__setattr__(self, "content_hash", content_digest(fingerprint))


@dataclass(frozen=True)
class RagChunk:
    """向量库和关系库共享的知识块契约。"""

    id: str
    doc_id: str
    title: str
    section: str
    chunk_index: int
    content: str
    category: str
    tags: Tuple[str, ...]
    aliases: Tuple[str, ...]
    source: str
    content_hash: str
    document_hash: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def tags_text(self) -> str:
        return ",".join(self.tags)

    @property
    def aliases_text(self) -> str:
        return ",".join(self.aliases)

    def vector_metadata(self) -> Dict[str, Any]:
        """Chroma 仅接受标量元数据，扩展字段也在这里统一收口。"""
        values: Dict[str, Any] = {
            "doc_id": self.doc_id,
            "title": self.title,
            "section": self.section,
            "chunk_index": self.chunk_index,
            "category": self.category,
            "tags": self.tags_text,
            "aliases": self.aliases_text,
            "source": self.source,
            "content_hash": self.content_hash,
            "document_hash": self.document_hash,
        }
        for key, value in self.metadata.items():
            if key not in values and isinstance(value, (str, int, float, bool)):
                values[key] = value
        return values

@dataclass(frozen=True)
class IngestionResult:
    doc_id: str
    status: str
    chunk_count: int
    document_hash: str
