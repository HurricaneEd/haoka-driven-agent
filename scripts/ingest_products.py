# -*- coding: utf-8 -*-
"""增量摄入 product 目录中的知识文档。

仅支持 .md 文件。默认按文档内容哈希跳过未变化文档，
变化时只替换对应 doc_id，不再清空整库。
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import DatabaseManager, SessionLocal, init_db
from app.knowledge_base import KnowledgeBaseManager
from app.rag.chunkers import ChunkingConfig, StructureAwareChunker
from app.rag.ingestion import IngestionService
from app.rag.parsers import DocumentParserRegistry
from config import settings

PRODUCT_DIR = Path(__file__).resolve().parents[1] / "product"


def build_local_pipeline() -> IngestionService:
    return IngestionService(
        store=None,
        parser_registry=DocumentParserRegistry(),
        chunker=StructureAwareChunker(ChunkingConfig(
            chunk_size=settings.rag_child_chunk_size,
            chunk_overlap=settings.rag_child_chunk_overlap,
        )),
    )


def sync_sqlite(prepared, path: Path) -> None:
    db = SessionLocal()
    try:
        manager = DatabaseManager(db)
        manager.upsert_knowledge_parent(prepared.document)
        manager.replace_knowledge_document(prepared.chunks)
        manager.upsert_knowledge_document(
            doc_id=prepared.document.doc_id,
            title=prepared.document.title,
            filename=path.name,
            source=prepared.document.source,
            category=prepared.document.category,
            tags=",".join(prepared.document.tags),
            chunk_count=len(prepared.chunks),
            file_size=path.stat().st_size,
            content_hash=prepared.document.content_hash,
            status="ready",
        )
    finally:
        db.close()


def delete_document(doc_id: str, kb: KnowledgeBaseManager | None) -> None:
    vector_count = kb.delete_document(doc_id) if kb else 0
    db = SessionLocal()
    try:
        manager = DatabaseManager(db)
        sqlite_count = manager.delete_knowledge_document(doc_id)
        manager.delete_knowledge_parent(doc_id)
        manager.delete_knowledge_document_record(doc_id)
    finally:
        db.close()
    print(f"已删除 {doc_id}：Chroma {vector_count} 块，SQLite {sqlite_count} 行")


def main() -> None:
    parser = argparse.ArgumentParser(description="产品知识库增量摄入")
    parser.add_argument(
        "--sqlite-only", action="store_true",
        help="只更新 SQLite 镜像，不连接 Embedding API 和 Chroma",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="即使文档哈希未变化，也重新生成向量",
    )
    parser.add_argument(
        "--delete-doc", metavar="DOC_ID",
        help="删除指定文档及其全部知识块，不执行目录摄入",
    )
    args = parser.parse_args()

    init_db()
    kb = None if args.sqlite_only else KnowledgeBaseManager()
    if args.delete_doc:
        delete_document(args.delete_doc, kb)
        return

    local_pipeline = build_local_pipeline()
    files = sorted(
        path for path in PRODUCT_DIR.iterdir()
        if path.is_file() and local_pipeline.parsers.supports(path)
    )
    if not files:
        supported = ", ".join(local_pipeline.parsers.supported_suffixes)
        print(f"未在 {PRODUCT_DIR} 找到支持的文档（{supported}）")
        sys.exit(1)

    indexed = skipped = failed = total_chunks = 0
    current_doc_ids: set[str] = set()
    for path in files:
        try:
            source = path.relative_to(PRODUCT_DIR.parent).as_posix()
            prepared = local_pipeline.prepare_file(
                path, {"category": "product", "source": source}
            )
            current_doc_ids.add(prepared.document.doc_id)
            if kb:
                result = kb.ingest(prepared, force=args.force)
                indexed += result.status == "indexed"
                skipped += result.status == "skipped"
                state = "已更新" if result.status == "indexed" else "未变化"
            else:
                state = "SQLite 已同步"
            sync_sqlite(prepared, path)
            total_chunks += len(prepared.chunks)
            print(f"{path.name}: {prepared.document.doc_id} -> {len(prepared.chunks)} 块（{state}）")
        except Exception as exc:
            failed += 1
            print(f"{path.name}: 摄入失败：{exc}")

    if not failed:
        db = SessionLocal()
        try:
            manager = DatabaseManager(db)
            stale = [
                record.doc_id for record in manager.get_knowledge_documents()
                if record.category == "product"
                and record.source.replace("\\", "/").startswith("product/")
                and record.doc_id not in current_doc_ids
            ]
        finally:
            db.close()
        for doc_id in stale:
            delete_document(doc_id, kb)

    print(f"完成：{len(files) - failed}/{len(files)} 份文档，共 {total_chunks} 块")
    if kb:
        print(f"向量更新 {indexed} 份，跳过 {skipped} 份；Chroma 共 {kb.count()} 块")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
