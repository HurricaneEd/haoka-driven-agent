"""SQLite 父文档存储。向量库只保存用于召回的子块。"""

import json
from typing import List, Optional

from app.database import DatabaseManager, SessionLocal
from app.rag.schemas import RagDocument


class SqliteParentStore:
    def upsert(self, document: RagDocument) -> None:
        db = SessionLocal()
        try:
            DatabaseManager(db).upsert_knowledge_parent(document)
        finally:
            db.close()

    def get(self, doc_id: str) -> Optional[RagDocument]:
        db = SessionLocal()
        try:
            row = DatabaseManager(db).get_knowledge_parent(doc_id)
            return self._to_document(row) if row else None
        finally:
            db.close()

    def list(self, category: str | None = None) -> List[RagDocument]:
        db = SessionLocal()
        try:
            rows = DatabaseManager(db).get_knowledge_parents(category)
            return [self._to_document(row) for row in rows]
        finally:
            db.close()

    def delete(self, doc_id: str) -> bool:
        db = SessionLocal()
        try:
            return DatabaseManager(db).delete_knowledge_parent(doc_id)
        finally:
            db.close()

    def clear(self) -> int:
        db = SessionLocal()
        try:
            return DatabaseManager(db).clear_knowledge_parents()
        finally:
            db.close()

    @staticmethod
    def _to_document(row) -> RagDocument:
        return RagDocument(
            doc_id=row.doc_id,
            title=row.title,
            content=row.content,
            source=row.source,
            category=row.category,
            tags=tuple(json.loads(row.tags or "[]")),
            aliases=tuple(json.loads(row.aliases or "[]")),
            content_hash=row.content_hash,
        )
