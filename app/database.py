from datetime import datetime, timezone
import uuid
from typing import Optional,List
import json

from sqlalchemy import create_engine, DateTime, Text, String, Integer, select, func, delete
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session
from config import settings

# Create database engine
engine = create_engine(settings.database_url, echo=settings.debug)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass


class UserAccount(Base):
    """Registered application user."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class AuthSession(Base):
    """Server-side authentication session keyed by a hashed bearer token."""
    __tablename__ = "auth_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Conversation(Base):
    """Database model for conversations."""
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc),onupdate=datetime.now(timezone.utc))


class Message(Base):
    """Database model for messages."""
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc))


# class KnowledgeBase(Base):
#     """Database model for knowledge base items."""
#     __tablename__ = "knowledge_base"
#
#     id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
#     title: Mapped[str] = mapped_column(String, nullable=False)
#     content: Mapped[str] = mapped_column(Text, nullable=False)
#     category: Mapped[str] = mapped_column(String, nullable=False)
#     tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string of tags
#     created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc))
#     updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc),onupdate=datetime.now(timezone.utc))
class KnowledgeBase(Base):
    """chunk 级知识镜像：一行 = Chroma 里的一个向量块。"""
    __tablename__ = "knowledge_base"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    # ↑ 与 Chroma id 一致，由 doc_id + 块内容哈希组成，章节前移时不会整体漂移。

    doc_id: Mapped[str] = mapped_column(String(64), index=True)   # 源文档标识（文件名或系统生成）
    title: Mapped[str] = mapped_column(String(128))               # 产品名（沿用原 title 字段）
    section: Mapped[str] = mapped_column(String(256))             # 结构路径，如 售后/注销
    chunk_index: Mapped[int] = mapped_column(Integer)             # 文档内块序号（0 起）
    content: Mapped[str] = mapped_column(Text)                    # 块文本（含产品名 + 标题）
    category: Mapped[str] = mapped_column(String(32), default="product")
    tags: Mapped[str | None] = mapped_column(Text, nullable=True) # 逗号分隔标量
    source: Mapped[str | None] = mapped_column(String(128))       # 源文件路径（溯源展示）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now)


class KnowledgeDocument(Base):
    """文档级台账：记录来源、处理状态和块数量。"""
    __tablename__ = "knowledge_documents"

    doc_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    source: Mapped[str] = mapped_column(String(512), nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="knowledge", index=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )


class KnowledgeParent(Base):
    """文档级父块：保存一份商品的完整 Markdown，供子块命中后展开。"""
    __tablename__ = "knowledge_parents"

    doc_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(512), nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="knowledge", index=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    aliases: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

def get_db() -> Session:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)



class DatabaseManager:
    """Database manager for CRUD operations."""

    def __init__(self, db: Session):
        self.db = db

    # 1. 创建操作
    def create_conversation(self, session_id: str, user_id: Optional[str] = None) -> Conversation:
        conversation = Conversation(session_id=session_id, user_id=user_id)
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    # 2. 查询单条记录
    def get_conversation(self, session_id: str, user_id: Optional[str] = None) -> Optional[Conversation]:
        stmt = select(Conversation).where(Conversation.session_id == session_id)
        if user_id is not None:
            stmt = stmt.where(Conversation.user_id == user_id)
        return self.db.execute(stmt).scalars().first()

    def get_user_by_email(self, email: str) -> Optional[UserAccount]:
        stmt = select(UserAccount).where(UserAccount.email == email)
        return self.db.execute(stmt).scalars().first()

    def create_user(self, email: str, password_hash: str) -> UserAccount:
        user = UserAccount(email=email, password_hash=password_hash)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def create_auth_session(self, token_hash: str, user_id: str, expires_at: datetime) -> AuthSession:
        session = AuthSession(
            token_hash=token_hash,
            user_id=user_id,
            expires_at=expires_at,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_user_by_token_hash(self, token_hash: str) -> Optional[UserAccount]:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        stmt = (
            select(UserAccount)
            .join(AuthSession, AuthSession.user_id == UserAccount.id)
            .where(AuthSession.token_hash == token_hash, AuthSession.expires_at > now)
        )
        return self.db.execute(stmt).scalars().first()

    def delete_auth_session(self, token_hash: str) -> None:
        session = self.db.get(AuthSession, token_hash)
        if session:
            self.db.delete(session)
            self.db.commit()

    def update_user_password(
        self,
        user_id: str,
        password_hash: str,
        keep_token_hash: Optional[str] = None,
    ) -> bool:
        user = self.db.get(UserAccount, user_id)
        if not user:
            return False
        user.password_hash = password_hash
        stmt = delete(AuthSession).where(AuthSession.user_id == user_id)
        if keep_token_hash:
            stmt = stmt.where(AuthSession.token_hash != keep_token_hash)
        self.db.execute(stmt)
        self.db.commit()
        return True

    # 3. 添加消息
    def add_message(self, conversation_id: str, role: str, content: str) -> Message:
        message = Message(conversation_id=conversation_id, role=role, content=content)
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    # 4. 查询列表
    def get_conversation_messages(self, conversation_id: str) -> List[Message]:
        stmt = select(Message).where(Message.conversation_id == conversation_id).order_by(Message.timestamp)
        return self.db.execute(stmt).scalars().all()

    # 4.5 清空某会话全部消息（Agent 改版后 clear 按 session 生效，数据库即真相）
    def clear_conversation_messages(self, session_id: str, user_id: Optional[str] = None) -> int:
        conversation = self.get_conversation(session_id, user_id)
        if not conversation:
            return 0
        stmt = select(Message).where(Message.conversation_id == conversation.id)
        messages = self.db.execute(stmt).scalars().all()
        for m in messages:
            self.db.delete(m)
        self.db.commit()
        return len(messages)

    # 5. 知识库添加（chunk 级镜像行，id 与 Chroma 1:1）
    def add_knowledge_item(self, chunk) -> KnowledgeBase:
        item = KnowledgeBase(
            id=chunk.id,
            doc_id=chunk.doc_id,
            title=chunk.title,
            section=chunk.section,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            category=chunk.category,
            tags=chunk.tags_text,
            source=chunk.source,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def replace_knowledge_document(self, chunks) -> List[KnowledgeBase]:
        """在一个事务中替换单份文档的 SQLite 镜像，不影响其他文档。"""
        chunks = list(chunks)
        if not chunks:
            return []
        doc_id = chunks[0].doc_id
        if any(chunk.doc_id != doc_id for chunk in chunks):
            raise ValueError("一次只能替换同一 doc_id 的知识块")
        existing = self.db.execute(
            select(KnowledgeBase)
            .where(KnowledgeBase.doc_id == doc_id)
            .order_by(KnowledgeBase.chunk_index)
        ).scalars().all()
        unchanged = len(existing) == len(chunks) and all(
            item.id == chunk.id
            and item.title == chunk.title
            and item.section == chunk.section
            and item.chunk_index == chunk.chunk_index
            and item.content == chunk.content
            and item.category == chunk.category
            and (item.tags or "") == chunk.tags_text
            and (item.source or "") == chunk.source
            for item, chunk in zip(existing, chunks)
        )
        if unchanged:
            return list(existing)
        self.db.execute(delete(KnowledgeBase).where(KnowledgeBase.doc_id == doc_id))
        items = [
            KnowledgeBase(
                id=chunk.id,
                doc_id=chunk.doc_id,
                title=chunk.title,
                section=chunk.section,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                category=chunk.category,
                tags=chunk.tags_text,
                source=chunk.source,
            )
            for chunk in chunks
        ]
        self.db.add_all(items)
        self.db.commit()
        return items

    def delete_knowledge_document(self, doc_id: str) -> int:
        result = self.db.execute(delete(KnowledgeBase).where(KnowledgeBase.doc_id == doc_id))
        self.db.commit()
        return result.rowcount or 0

    def upsert_knowledge_parent(self, document) -> KnowledgeParent:
        parent = self.db.get(KnowledgeParent, document.doc_id)
        if not parent:
            parent = KnowledgeParent(doc_id=document.doc_id, created_at=datetime.now())
            self.db.add(parent)
        parent.title = document.title
        parent.content = document.content
        parent.source = document.source
        parent.category = document.category
        parent.tags = json.dumps(list(document.tags), ensure_ascii=False)
        parent.aliases = json.dumps(list(document.aliases), ensure_ascii=False)
        parent.content_hash = document.content_hash
        parent.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(parent)
        return parent

    def get_knowledge_parent(self, doc_id: str) -> Optional[KnowledgeParent]:
        return self.db.get(KnowledgeParent, doc_id)

    def get_knowledge_parents(self, category: Optional[str] = None) -> List[KnowledgeParent]:
        stmt = select(KnowledgeParent)
        if category:
            stmt = stmt.where(KnowledgeParent.category == category)
        return list(self.db.execute(stmt.order_by(KnowledgeParent.title)).scalars().all())

    def delete_knowledge_parent(self, doc_id: str) -> bool:
        parent = self.db.get(KnowledgeParent, doc_id)
        if not parent:
            return False
        self.db.delete(parent)
        self.db.commit()
        return True

    def clear_knowledge_parents(self) -> int:
        result = self.db.execute(delete(KnowledgeParent))
        self.db.commit()
        return result.rowcount or 0

    def create_knowledge_document(
        self,
        *,
        doc_id: str,
        title: str,
        filename: str,
        source: str,
        category: str,
        tags: str,
        file_size: int,
        created_by: Optional[str],
    ) -> KnowledgeDocument:
        document = KnowledgeDocument(
            doc_id=doc_id,
            title=title,
            filename=filename,
            source=source,
            category=category,
            tags=tags,
            status="pending",
            file_size=file_size,
            created_by=created_by,
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def get_knowledge_document(self, doc_id: str) -> Optional[KnowledgeDocument]:
        return self.db.get(KnowledgeDocument, doc_id)

    def get_knowledge_documents(self) -> List[KnowledgeDocument]:
        stmt = select(KnowledgeDocument).order_by(
            KnowledgeDocument.updated_at.desc(), KnowledgeDocument.created_at.desc()
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_document_chunks(self, doc_id: str) -> List[KnowledgeBase]:
        stmt = (
            select(KnowledgeBase)
            .where(KnowledgeBase.doc_id == doc_id)
            .order_by(KnowledgeBase.chunk_index)
        )
        return list(self.db.execute(stmt).scalars().all())

    def set_knowledge_document_status(
        self,
        doc_id: str,
        status: str,
        *,
        chunk_count: Optional[int] = None,
        content_hash: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Optional[KnowledgeDocument]:
        document = self.get_knowledge_document(doc_id)
        if not document:
            return None
        document.status = status
        document.error_message = error_message
        if chunk_count is not None:
            document.chunk_count = chunk_count
        if content_hash is not None:
            document.content_hash = content_hash
        document.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(document)
        return document

    def upsert_knowledge_document(
        self,
        *,
        doc_id: str,
        title: str,
        filename: str,
        source: str,
        category: str,
        tags: str,
        chunk_count: int,
        file_size: int,
        content_hash: str,
        status: str = "ready",
        created_by: Optional[str] = None,
    ) -> KnowledgeDocument:
        document = self.get_knowledge_document(doc_id)
        if not document:
            document = KnowledgeDocument(doc_id=doc_id, created_at=datetime.now())
            self.db.add(document)
        document.title = title
        document.filename = filename
        document.source = source
        document.category = category
        document.tags = tags
        document.status = status
        document.chunk_count = chunk_count
        document.file_size = file_size
        document.content_hash = content_hash
        document.error_message = None
        if created_by is not None:
            document.created_by = created_by
        document.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(document)
        return document

    def delete_knowledge_document_record(self, doc_id: str) -> bool:
        document = self.get_knowledge_document(doc_id)
        if not document:
            return False
        self.db.delete(document)
        self.db.commit()
        return True

    # 6. 条件查询列表
    def get_knowledge_items(self, category: Optional[str] = None) -> List[KnowledgeBase]:
        stmt = select(KnowledgeBase)
        if category:
            stmt = stmt.where(KnowledgeBase.category == category)
        return self.db.execute(stmt).scalars().all()
