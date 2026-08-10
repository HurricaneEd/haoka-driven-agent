# -*- coding: utf-8 -*-
"""产品知识库入库脚本（清空重建，幂等可重跑）。

双写：Chroma（检索大脑） + SQLite knowledge_base（台账/镜像），两库 1:1。

用法：
    python scripts/ingest_products.py                # Chroma + SQLite 双写
    python scripts/ingest_products.py --sqlite-only  # 只写 SQLite（无 API Key 时调试切分/入库）

流程：
    1. 清空 Chroma 集合 + SQLite knowledge_base 表
    2. 遍历 product/*.md → MarkdownHeaderTextSplitter 切分 → 组装 Chunk
    3. 双写：Chroma add_texts + SQLite 逐行插入（id 完全一致）
"""
import argparse
import sys
from pathlib import Path

# 保证从任意 cwd 启动都能 import config / app
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete

from app.database import SessionLocal, KnowledgeBase, init_db
from app.knowledge_base import KnowledgeBaseManager
from app.split.split import split_product_file

PRODUCT_DIR = Path(__file__).resolve().parents[1] / "product"


def clear_sqlite() -> None:
    """清空 SQLite knowledge_base 表（幂等）。"""
    db = SessionLocal()
    try:
        db.execute(delete(KnowledgeBase))
        db.commit()
        print("SQLite: knowledge_base 已清空")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="产品知识库入库（清空重建，幂等可重跑）")
    parser.add_argument("--sqlite-only", action="store_true",
                        help="只写 SQLite，跳过 Chroma（无 API Key 时调试用）")
    args = parser.parse_args()

    md_files = sorted(PRODUCT_DIR.glob("*.md"))
    if not md_files:
        print(f"✗ 未在 {PRODUCT_DIR} 找到任何 .md 文件")
        sys.exit(1)

    init_db()  # 确保表存在

    kb = None
    if not args.sqlite_only:
        kb = KnowledgeBaseManager()
        kb.clear_all()
        print("Chroma: knowledge_base 集合已清空")
    clear_sqlite()

    total = 0
    db = SessionLocal()
    try:
        for path in md_files:
            fm, chunks = split_product_file(path)
            print(f"  {path.name}: doc_id={fm.get('doc_id')} -> {len(chunks)} 块")

            if kb is not None:
                kb.add_chunks(chunks)

            db.add_all([
                KnowledgeBase(
                    id=c.id,
                    doc_id=c.doc_id,
                    title=c.title,
                    section=c.section,
                    chunk_index=c.chunk_index,
                    content=c.content,
                    category=c.category,
                    tags=c.tags,
                    source=c.source,
                )
                for c in chunks
            ])
            total += len(chunks)
        db.commit()
    finally:
        db.close()

    print(f"✓ 完成：{len(md_files)} 份文档，共 {total} 块")
    if kb is not None:
        print(f"  Chroma 集合 count = {kb.count()}")
    print("  SQLite knowledge_base 行数 = ", end="")
    db = SessionLocal()
    try:
        from sqlalchemy import func, select
        rows = db.execute(select(func.count()).select_from(KnowledgeBase)).scalar()
        print(rows)
    finally:
        db.close()


if __name__ == "__main__":
    main()
