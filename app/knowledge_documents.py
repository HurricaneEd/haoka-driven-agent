"""知识文档上传、处理、重试和删除的应用服务。"""

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Dict
import uuid

from fastapi import UploadFile

from app.database import DatabaseManager, SessionLocal
from app.knowledge_base import get_knowledge_base
from app.rag.parsers import DocumentParserRegistry
from config import BASE_DIR, settings


class KnowledgeUploadError(ValueError):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class SavedUpload:
    doc_id: str
    filename: str
    source: str
    size: int


_document_locks: Dict[str, Lock] = {}
_locks_guard = Lock()


def _document_lock(doc_id: str) -> Lock:
    with _locks_guard:
        return _document_locks.setdefault(doc_id, Lock())


def upload_root() -> Path:
    root = Path(settings.knowledge_upload_path).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_source(source: str) -> Path:
    path = Path(source)
    return path.resolve() if path.is_absolute() else (BASE_DIR / path).resolve()


def source_name(path: Path) -> str:
    try:
        return path.resolve().relative_to(BASE_DIR.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


async def save_upload(upload: UploadFile) -> SavedUpload:
    filename = Path(upload.filename or "").name.strip()
    if not filename:
        raise KnowledgeUploadError("请选择要上传的文件")
    suffix = Path(filename).suffix.lower()
    registry = DocumentParserRegistry()
    if suffix not in registry.supported_suffixes:
        supported = "、".join(value.lstrip(".").upper() for value in registry.supported_suffixes)
        raise KnowledgeUploadError(f"暂不支持 {suffix or '无扩展名'} 文件；支持 {supported}")

    doc_id = f"upload-{uuid.uuid4().hex[:16]}"
    destination = upload_root() / f"{doc_id}{suffix}"
    max_bytes = settings.knowledge_upload_max_mb * 1024 * 1024
    total = 0
    try:
        with destination.open("xb") as output:
            while data := await upload.read(1024 * 1024):
                total += len(data)
                if total > max_bytes:
                    raise KnowledgeUploadError(
                        f"文件不能超过 {settings.knowledge_upload_max_mb} MB", status_code=413
                    )
                output.write(data)
        if total == 0:
            raise KnowledgeUploadError("上传文件为空")
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

    return SavedUpload(
        doc_id=doc_id,
        filename=filename,
        source=source_name(destination),
        size=total,
    )


def process_knowledge_document(doc_id: str) -> None:
    """后台执行解析和向量化；错误写回台账而不逃逸到请求线程。"""
    with _document_lock(doc_id):
        db = SessionLocal()
        manager = DatabaseManager(db)
        try:
            record = manager.get_knowledge_document(doc_id)
            if not record:
                return
            manager.set_knowledge_document_status(doc_id, "processing", error_message=None)
            path = resolve_source(record.source)
            if not path.is_file():
                raise FileNotFoundError(f"源文件不存在：{record.filename}")

            prepared = get_knowledge_base().prepare_file(path, {
                "doc_id": record.doc_id,
                "title": record.title,
                "category": record.category,
                "tags": record.tags or "",
                "source": record.source,
            })
            get_knowledge_base().ingest(prepared)
            manager.replace_knowledge_document(prepared.chunks)
            manager.upsert_knowledge_document(
                doc_id=record.doc_id,
                title=prepared.document.title,
                filename=record.filename,
                source=record.source,
                category=prepared.document.category,
                tags=",".join(prepared.document.tags),
                chunk_count=len(prepared.chunks),
                file_size=record.file_size,
                content_hash=prepared.document.content_hash,
                status="ready",
                created_by=record.created_by,
            )
        except Exception as exc:
            db.rollback()
            manager.set_knowledge_document_status(
                doc_id,
                "error",
                error_message=str(exc)[:1000],
            )
        finally:
            db.close()


def delete_knowledge_document(doc_id: str) -> bool:
    with _document_lock(doc_id):
        db = SessionLocal()
        manager = DatabaseManager(db)
        try:
            record = manager.get_knowledge_document(doc_id)
            if not record:
                return False
            source = record.source
            get_knowledge_base().delete_document(doc_id)
            manager.delete_knowledge_document(doc_id)
            manager.delete_knowledge_document_record(doc_id)

            path = resolve_source(source)
            root = upload_root()
            if path.is_relative_to(root):
                path.unlink(missing_ok=True)
            return True
        finally:
            db.close()
