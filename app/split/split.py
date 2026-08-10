# -*- coding: utf-8 -*-
"""产品文档切分模块。

把 product/*.md 按 Markdown 标题结构切成「一块 = 一个语义节」，
组装成与 SQLite knowledge_base / ChromaDB 严格对齐的 Chunk。

关键约定（详见 knowledge-ingestion-plan.md）：
- frontmatter 声明 doc_id / category / tags（产品文件用 ```markdown 围栏包裹）
- 每个 `##` 节 = 一个 chunk；`###` 子节不新增列，用 `/` 合并进 section
- 每块 content 统一前置产品名，避免 5 份文档节名相同导致检索串卡
- id = f"{doc_id}_c{chunk_index}"，SQLite 主键 ↔ Chroma id 完全一致
"""
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Dict, List, Tuple

import yaml
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter


@dataclass
class Chunk:
    """知识块：SQLite 一行 ↔ Chroma 一个向量。"""
    id: str              # f"{doc_id}_c{chunk_index}"
    doc_id: str          # frontmatter 声明的稳定 slug
    title: str           # 产品名（# 标题去 ** 残留）
    section: str         # 节名；### 用 / 合并（如 复机及注销方式/注销方式）
    chunk_index: int     # 文档内块序号（0 起）
    content: str         # 产品名 + 标题 + 节内容
    category: str        # 默认 product
    tags: str            # 逗号分隔标量（chromadb 只接受标量值）
    source: str          # 源文件相对路径（溯源展示，非标识）

    def metadata(self) -> Dict[str, Any]:
        """Chroma 侧元数据：键与 SQLite 列名一致（见方案 6.2 同步契约）。"""
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "section": self.section,
            "chunk_index": self.chunk_index,
            "category": self.category,
            "tags": self.tags,
            "source": self.source,
        }


# 当前产品文件 frontmatter 外层有 ```markdown 围栏；也兼容裸 --- 写法
_FM_FENCE_RE = re.compile(r"^```markdown\s*\n---\n(.*?)\n---\n```\s*\n?(.*)$", re.S)
_FM_BARE_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)


def split_frontmatter(md: str) -> Tuple[Dict[str, Any], str]:
    """剥离 frontmatter，返回 (frontmatter dict, markdown 正文)。

    ⚠️ 围栏必须整体剥掉：若残留 ` ``` `，MarkdownHeaderTextSplitter 会
    把整篇文档当成代码块，只产出 1 个 chunk。
    """
    m = _FM_FENCE_RE.match(md) or _FM_BARE_RE.match(md)
    if not m:
        return {}, md
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


def _clean_product(raw: str) -> str:
    """清理 # 标题里的 markdown 加粗残留（**）。"""
    return re.sub(r"\*\*", "", raw).strip()


def split_product_file(path: Path) -> Tuple[Dict[str, Any], List[Chunk]]:
    """读一个产品 md，切成 Chunk 列表。返回 (frontmatter, chunks)。"""
    md = path.read_text(encoding="utf-8")
    fm, body = split_frontmatter(md)

    doc_id = str(fm.get("doc_id", path.stem))
    category = str(fm.get("category", "product"))
    tags = str(fm.get("tags", ""))

    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "product"), ("##", "section"), ("###", "subsection")],
        strip_headers=False,  # 标题保留进正文，块自含上下文
    )
    docs: List[Document] = splitter.split_text(body)
    if not docs:  # 极端情况：正文无任何标题，整篇当一块
        docs = [Document(page_content=body, metadata={})]

    # 产品名取自 # 标题；首块 metadata['product'] 里就是它（strip **）
    product = _clean_product(docs[0].metadata.get("product", ""))
    if not product:
        product = path.stem

    # 溯源路径：优先相对当前工作目录（product/xxx.md），可移植
    try:
        source = str(path.relative_to(Path.cwd())).replace("\\", "/")
    except ValueError:
        source = str(path).replace("\\", "/")

    chunks: List[Chunk] = []
    for i, doc in enumerate(docs):
        section = doc.metadata.get("section", "")
        subsection = doc.metadata.get("subsection")
        if subsection and section:
            section = f"{section}/{subsection}"
        content = f"{product}\n{doc.page_content.replace('**', '')}"
        chunks.append(Chunk(
            id=f"{doc_id}_c{i}",
            doc_id=doc_id,
            title=product,
            section=section,
            chunk_index=i,
            content=content,
            category=category,
            tags=tags,
            source=source,
        ))
    return fm, chunks
