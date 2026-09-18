"""结构优先、长度兜底的知识切分策略。"""

from collections import defaultdict
from dataclasses import dataclass
import re
from typing import List, Tuple

from app.rag.schemas import RagChunk, RagDocument, content_digest


@dataclass(frozen=True)
class ChunkingConfig:
    chunk_size: int = 800
    chunk_overlap: int = 120
    separators: Tuple[str, ...] = ("\n\n", "\n", "。", "！", "？", "；", "，", " ")

    def __post_init__(self) -> None:
        if self.chunk_size < 128:
            raise ValueError("chunk_size 不能小于 128")
        if self.chunk_overlap < 0 or self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap 必须大于等于 0 且小于 chunk_size")


@dataclass(frozen=True)
class _Section:
    name: str
    content: str


class StructureAwareChunker:
    """先按 Markdown 标题保留语义结构，超长章节再递归切分。"""

    _heading_re = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

    def __init__(self, config: ChunkingConfig | None = None) -> None:
        self.config = config or ChunkingConfig()

    def split(self, document: RagDocument) -> List[RagChunk]:
        chunks: list[RagChunk] = []
        duplicate_counts: defaultdict[str, int] = defaultdict(int)
        for section in self._sections(document.content):
            prefix_parts = [document.title]
            if section.name and section.name != document.title:
                prefix_parts.append(section.name)
            prefix = "\n".join(prefix_parts).strip()
            available = max(64, self.config.chunk_size - len(prefix) - 1)
            overlap = min(self.config.chunk_overlap, max(0, available - 1))
            fragments = self._split_text(section.content, available, overlap)
            for fragment in fragments:
                content = f"{prefix}\n{fragment}".strip() if prefix else fragment.strip()
                if not content:
                    continue
                digest = content_digest(f"{section.name}\n{content}")
                duplicate_index = duplicate_counts[digest]
                duplicate_counts[digest] += 1
                suffix = digest[:20] if duplicate_index == 0 else f"{digest[:16]}-{duplicate_index}"
                chunks.append(RagChunk(
                    id=f"{document.doc_id}_{suffix}",
                    doc_id=document.doc_id,
                    title=document.title,
                    section=section.name,
                    chunk_index=len(chunks),
                    content=content,
                    category=document.category,
                    tags=document.tags,
                    source=document.source,
                    content_hash=digest,
                    document_hash=document.content_hash,
                    metadata=document.metadata,
                ))
        if not chunks:
            raise ValueError(f"文档 {document.doc_id} 切分后没有有效知识块")
        return chunks

    def _sections(self, text: str) -> List[_Section]:
        hierarchy: dict[int, str] = {}
        current_name = ""
        current_lines: list[str] = []
        sections: list[_Section] = []
        fence_marker = ""

        def flush() -> None:
            content = "\n".join(current_lines).strip()
            if content:
                sections.append(_Section(current_name, content))

        for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            stripped = line.strip()
            if stripped.startswith(("```", "~~~")):
                marker = stripped[:3]
                fence_marker = "" if fence_marker == marker else (marker if not fence_marker else fence_marker)
                current_lines.append(line)
                continue
            match = None if fence_marker else self._heading_re.match(stripped)
            if not match:
                current_lines.append(line)
                continue
            level = len(match.group(1))
            heading = re.sub(r"[*_`]", "", match.group(2)).strip()
            if level == 1:
                if current_lines:
                    flush()
                    current_lines = []
                hierarchy = {1: heading}
                current_name = ""
                continue
            flush()
            current_lines = []
            hierarchy[level] = heading
            hierarchy = {key: value for key, value in hierarchy.items() if key <= level}
            current_name = "/".join(hierarchy[key] for key in sorted(hierarchy) if key >= 2)
        flush()
        return sections or [_Section("", text.strip())]

    def _split_text(self, text: str, limit: int, overlap: int) -> List[str]:
        clean = text.strip()
        if not clean:
            return []
        if len(clean) <= limit:
            return [clean]

        result: list[str] = []
        start = 0
        length = len(clean)
        while start < length:
            hard_end = min(length, start + limit)
            end = hard_end
            if hard_end < length:
                minimum = start + max(1, limit // 2)
                candidates = []
                for separator in self.config.separators:
                    position = clean.rfind(separator, minimum, hard_end)
                    if position >= minimum:
                        candidates.append(position + len(separator))
                if candidates:
                    end = max(candidates)
            fragment = clean[start:end].strip()
            if fragment:
                result.append(fragment)
            if end >= length:
                break
            next_start = max(start + 1, end - overlap)
            while next_start < end and clean[next_start].isspace():
                next_start += 1
            start = next_start
        return result
