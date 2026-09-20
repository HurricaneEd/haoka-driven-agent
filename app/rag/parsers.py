"""Markdown 知识文档解析器。"""

import re
from pathlib import Path
from typing import Any, Dict, Tuple

from app.rag.identity import derive_document_aliases, normalize_aliases
from app.rag.schemas import RagDocument, normalize_tags


class UnsupportedDocumentError(ValueError):
    pass


_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.M)


def _clean_heading(value: str) -> str:
    return re.sub(r"[*_`#]", "", value).strip()


def _relative_source(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _build_document(
    path: Path,
    content: str,
    metadata: Dict[str, Any],
    detected_title: str = "",
) -> RagDocument:
    doc_id = str(metadata.get("doc_id") or path.stem)
    title = str(metadata.get("title") or detected_title or path.stem)
    category = str(metadata.get("category") or "knowledge")
    source = str(metadata.get("source") or _relative_source(path)).replace("\\", "/")
    known = {"doc_id", "title", "category", "tags", "aliases", "source"}
    extra = {key: value for key, value in metadata.items() if key not in known}
    aliases = normalize_aliases(metadata.get("aliases")) or derive_document_aliases(title, doc_id)
    return RagDocument(
        doc_id=doc_id,
        title=_clean_heading(title),
        content=content,
        source=source,
        category=category,
        tags=normalize_tags(metadata.get("tags")),
        aliases=aliases,
        metadata=extra,
    )


class MarkdownParser:
    suffixes = (".md",)

    def parse(self, path: Path, metadata: Dict[str, Any] | None = None) -> RagDocument:
        body = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
        merged = metadata or {}
        match = _H1_RE.search(body)
        title = _clean_heading(match.group(1)) if match else path.stem
        return _build_document(path, body, merged, title)


class DocumentParserRegistry:
    def __init__(self) -> None:
        parser = MarkdownParser()
        self._parsers = {suffix: parser for suffix in parser.suffixes}

    @property
    def supported_suffixes(self) -> Tuple[str, ...]:
        return tuple(sorted(self._parsers))

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in self._parsers

    def parse(self, path: Path, metadata: Dict[str, Any] | None = None) -> RagDocument:
        parser = self._parsers.get(path.suffix.lower())
        if not parser:
            supported = ", ".join(self.supported_suffixes)
            raise UnsupportedDocumentError(f"不支持 {path.suffix or '无扩展名'} 文件；支持：{supported}")
        return parser.parse(path, metadata)
