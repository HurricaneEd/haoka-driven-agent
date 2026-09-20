"""旧切分入口的兼容层。

新代码请直接使用 app.rag；保留本模块是为了让已有导入路径平滑迁移。
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.rag.chunkers import ChunkingConfig, StructureAwareChunker
from app.rag.parsers import DocumentParserRegistry
from app.rag.schemas import RagChunk
from config import settings

Chunk = RagChunk


def split_product_file(path: Path) -> Tuple[Dict[str, Any], List[RagChunk]]:
    project_root = Path(__file__).resolve().parents[1]
    try:
        source = path.resolve().relative_to(project_root).as_posix()
    except ValueError:
        source = path.resolve().as_posix()
    document = DocumentParserRegistry().parse(
        path, {"category": "product", "source": source}
    )
    chunker = StructureAwareChunker(ChunkingConfig(
        chunk_size=settings.rag_child_chunk_size,
        chunk_overlap=settings.rag_child_chunk_overlap,
    ))
    return {}, chunker.split(document)
