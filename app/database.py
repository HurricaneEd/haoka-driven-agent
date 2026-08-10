from datetime import datetime, timezone
import uuid
from typing import Optional,List

from sqlalchemy import create_engine, DateTime, Text, String, Integer,select,func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session
from config import settings

# Create database engine
engine = create_engine(settings.database_url, echo=settings.debug)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass


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

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # ↑ 与 Chroma id 一致：f"{doc_id}_c{chunk_index}"，如 "guangdian-shengyu_c5"

    doc_id: Mapped[str] = mapped_column(String(64), index=True)   # 源文档标识（frontmatter）
    title: Mapped[str] = mapped_column(String(128))               # 产品名（沿用原 title 字段）
    section: Mapped[str] = mapped_column(String(64))              # 节名（### 用 / 合并）
    chunk_index: Mapped[int] = mapped_column(Integer)             # 文档内块序号（0 起）
    content: Mapped[str] = mapped_column(Text)                    # 块文本（含产品名 + 标题）
    category: Mapped[str] = mapped_column(String(32), default="product")
    tags: Mapped[str | None] = mapped_column(Text, nullable=True) # 逗号分隔标量
    source: Mapped[str | None] = mapped_column(String(128))       # 源文件路径（溯源展示）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now)

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
    def get_conversation(self, session_id: str) -> Optional[Conversation]:
        stmt = select(Conversation).where(Conversation.session_id == session_id)
        return self.db.execute(stmt).scalars().first()

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

    # 5. 知识库添加
    def add_knowledge_item(self, title: str, content: str, category: str,
                           tags: Optional[List[str]] = None) -> KnowledgeBase:
        tags_json = ",".join(tags) if tags else ""
        item = KnowledgeBase(title=title, content=content, category=category, tags=tags_json)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    # 6. 条件查询列表
    def get_knowledge_items(self, category: Optional[str] = None) -> List[KnowledgeBase]:
        stmt = select(KnowledgeBase)
        if category:
            stmt = stmt.where(KnowledgeBase.category == category)
        return self.db.execute(stmt).scalars().all()